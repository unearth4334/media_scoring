"""Metadata extraction and storage service."""

import hashlib
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Optional, Any

from ..state import get_state
from ..utils.png_chunks import read_png_parameters_text
from ..utils.prompt_parser import parse_png_prompt_text

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import imagehash
except ImportError:
    imagehash = None

logger = logging.getLogger(__name__)


def extract_and_store_metadata(file_path: Path) -> Optional[Dict[str, Any]]:
    """Extract metadata from a media file and store it in the database."""
    state = get_state()
    
    if not state.database_enabled:
        return None
    
    try:
        metadata = extract_metadata(file_path)
        if metadata:
            with state.get_database_service() as db:
                db.store_media_metadata(file_path, metadata)
                logger.debug(f"Stored metadata for {file_path.name}")
        return metadata
    except Exception as e:
        logger.error(f"Failed to extract/store metadata for {file_path}: {e}")
        return None


def extract_metadata(file_path: Path) -> Dict[str, Any]:
    """Extract metadata from a media file."""
    metadata = {}
    ext = file_path.suffix.lower()
    
    try:
        # Get file stats
        stat = file_path.stat()
        metadata['file_size'] = stat.st_size
        metadata['file_modified_at'] = stat.st_mtime
        
        if ext == ".mp4":
            metadata.update(extract_video_metadata(file_path))
        elif ext in {".png", ".jpg", ".jpeg"}:
            metadata.update(extract_image_metadata(file_path))
            
        # Extract AI-related keywords from metadata
        keywords = extract_keywords_from_metadata(metadata)
        if keywords:
            metadata['extracted_keywords'] = keywords
            
    except Exception as e:
        logger.error(f"Error extracting metadata from {file_path}: {e}")
        metadata['error'] = str(e)
    
    return metadata


def extract_video_metadata(file_path: Path) -> Dict[str, Any]:
    """Extract metadata from video files using ffprobe."""
    metadata = {}
    
    try:
        # Basic video info
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "video:0", 
            "-show_entries", "stream=width,height,duration,r_frame_rate",
            "-of", "json", str(file_path)
        ]
        cp = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = json.loads(cp.stdout or "{}")
        
        if isinstance(info, dict) and info.get("streams"):
            stream = info["streams"][0]
            
            if "width" in stream:
                metadata["width"] = int(stream["width"])
            if "height" in stream:
                metadata["height"] = int(stream["height"])
            if "duration" in stream:
                metadata["duration"] = float(stream["duration"])
            if "r_frame_rate" in stream:
                # Parse frame rate (e.g., "30/1" -> 30.0)
                rate_str = stream["r_frame_rate"]
                if "/" in rate_str:
                    num, den = rate_str.split("/")
                    metadata["frame_rate"] = float(num) / float(den)
        
        # Try to extract AI workflow data from metadata
        workflow_data = extract_workflow_from_video(file_path)
        if workflow_data:
            metadata.update(workflow_data)
            
    except subprocess.CalledProcessError as e:
        logger.warning(f"ffprobe failed for {file_path}: {e}")
    except Exception as e:
        logger.error(f"Error extracting video metadata: {e}")
    
    return metadata


def extract_image_metadata(file_path: Path) -> Dict[str, Any]:
    """Extract metadata from image files."""
    metadata = {}
    ext = file_path.suffix.lower()
    
    try:
        if Image is None:
            metadata["error"] = "Pillow not installed"
            return metadata
        
        with Image.open(file_path) as img:
            metadata["width"] = img.width
            metadata["height"] = img.height
            metadata["color_mode"] = img.mode
            metadata["has_alpha"] = img.mode in ("RGBA", "LA")
        
        # Extract PNG text parameters (common in AI-generated images)
        if ext == ".png":
            png_text = read_png_parameters_text(file_path)
            if png_text:
                metadata["png_text"] = png_text
                
                # Try to parse AI generation parameters
                ai_params = parse_ai_parameters(png_text)
                if ai_params:
                    metadata.update(ai_params)
                    
    except Exception as e:
        logger.error(f"Error extracting image metadata: {e}")
        metadata["error"] = str(e)
    
    return metadata


def extract_workflow_from_video(file_path: Path) -> Dict[str, Any]:
    """Extract ComfyUI workflow data from video metadata."""
    workflow_data = {}
    
    try:
        # Use ffprobe to get all metadata
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format_tags",
            "-of", "json", str(file_path)
        ]
        cp = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = json.loads(cp.stdout or "{}")
        
        if isinstance(info, dict) and info.get("format", {}).get("tags"):
            tags = info["format"]["tags"]
            
            # Look for workflow data in various tag fields
            for tag_key, tag_value in tags.items():
                if "workflow" in tag_key.lower() or "comfyui" in tag_key.lower():
                    try:
                        workflow_json = json.loads(tag_value)
                        workflow_data["workflow_data"] = workflow_json
                        break
                    except json.JSONDecodeError:
                        continue
            
            # Extract prompt information if available
            for key in ["prompt", "positive", "description"]:
                if key in tags:
                    workflow_data["prompt"] = tags[key]
                    break
            
            for key in ["negative_prompt", "negative"]:
                if key in tags:
                    workflow_data["negative_prompt"] = tags[key]
                    break
                    
    except Exception as e:
        logger.debug(f"No workflow data found in {file_path}: {e}")
    
    return workflow_data


def parse_ai_parameters(png_text: str) -> Dict[str, Any]:
    """Parse AI generation parameters from PNG text."""
    ai_params = {}
    
    try:
        # Use the new prompt parser to extract keywords and LoRAs
        parsed_prompt = parse_png_prompt_text(png_text)
        
        # Store the raw prompts
        if parsed_prompt.raw_positive:
            ai_params["prompt"] = parsed_prompt.raw_positive
        if parsed_prompt.raw_negative:
            ai_params["negative_prompt"] = parsed_prompt.raw_negative
        
        # Store the parsed prompt data for the database
        ai_params["parsed_prompt_data"] = {
            "positive_keywords": parsed_prompt.positive_keywords,
            "negative_keywords": parsed_prompt.negative_keywords,
            "loras": parsed_prompt.loras
        }
        
        # Also try to parse structured parameters (e.g., from Auto1111)
        parsed_params = parse_auto1111_parameters(png_text)
        ai_params.update(parsed_params)
                
    except Exception as e:
        logger.debug(f"Failed to parse AI parameters: {e}")
    
    return ai_params


def parse_auto1111_parameters(param_string: str) -> Dict[str, Any]:
    """Parse Auto1111-style parameter strings."""
    params = {}
    
    try:
        # Split on common delimiters
        lines = param_string.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Look for key: value patterns
            if ': ' in line:
                # Handle the first line specially if it contains comma-separated parameters
                if line.startswith(('Steps:', 'Sampler:', 'Schedule type:')):
                    # Parse comma-separated parameters line
                    params.update(_parse_comma_separated_parameters(line))
                else:
                    # Handle simple key: value pairs
                    key, value = line.split(': ', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Map to our schema with proper data types
                    params.update(_map_parameter_to_schema(key, value))
                    
        # Look for prompt at the beginning (if it's not a parameter line)
        if lines and not ': ' in lines[0]:
            params["prompt"] = lines[0].strip()
            
    except Exception as e:
        logger.debug(f"Failed to parse Auto1111 parameters: {e}")
    
    return params


def _parse_comma_separated_parameters(param_line: str) -> Dict[str, Any]:
    """Parse comma-separated parameter strings like 'Steps: 30, Sampler: DPM++ 3M SDE, ...'"""
    params = {}
    
    try:
        # Split by comma and parse each key: value pair
        parts = param_line.split(', ')
        
        for part in parts:
            part = part.strip()
            if ': ' in part:
                key, value = part.split(': ', 1)
                key = key.strip()
                value = value.strip()
                
                # Map to our schema
                params.update(_map_parameter_to_schema(key, value))
                
    except Exception as e:
        logger.debug(f"Failed to parse comma-separated parameters: {e}")
    
    return params


def _map_parameter_to_schema(key: str, value: str) -> Dict[str, Any]:
    """Map a parameter key-value pair to our database schema with proper data types."""
    params = {}
    key_lower = key.lower().strip()
    value = value.strip()
    
    try:
        # Integer fields
        if key_lower in ["steps"]:
            params["steps"] = int(value) if value.isdigit() else None
        
        # Float fields  
        elif key_lower in ["cfg scale"]:
            params["cfg_scale"] = float(value)
        elif key_lower in ["denoising strength"]:
            params["denoising_strength"] = float(value)
        elif key_lower in ["hires cfg scale"]:
            if "hires_config" not in params:
                params["hires_config"] = {}
            params["hires_config"]["cfg_scale"] = float(value)
        elif key_lower in ["hires upscale"]:
            if "hires_config" not in params:
                params["hires_config"] = {}
            params["hires_config"]["upscale"] = float(value)
        elif key_lower.startswith("dynthres_") and key_lower.endswith(("_scale", "_scale_min", "_threshold_percentile", "_sched_val", "_interpolate_phi")):
            if "dynthres_config" not in params:
                params["dynthres_config"] = {}
            # Remove the dynthres_ prefix for cleaner JSON
            clean_key = key_lower[9:]  # Remove "dynthres_" prefix
            params["dynthres_config"][clean_key] = float(value)
        
        # String fields
        elif key_lower in ["sampler"]:
            params["sampler"] = value
        elif key_lower in ["schedule type"]:
            params["schedule_type"] = value
        elif key_lower in ["seed"]:
            params["seed"] = value
        elif key_lower in ["size"]:
            params["size"] = value
        elif key_lower in ["model"]:
            params["model_name"] = value
        elif key_lower in ["model hash"]:
            params["model_hash"] = value
        elif key_lower in ["hires module 1"]:
            if "hires_config" not in params:
                params["hires_config"] = {}
            params["hires_config"]["module_1"] = value
        elif key_lower in ["hires upscaler"]:
            if "hires_config" not in params:
                params["hires_config"] = {}
            params["hires_config"]["upscaler"] = value
        elif key_lower in ["version"]:
            params["version"] = value
        elif key_lower in ["lora hashes"]:
            params["lora_hashes"] = value
        
        # Boolean fields
        elif key_lower in ["dynthres_enabled"]:
            if "dynthres_config" not in params:
                params["dynthres_config"] = {}
            params["dynthres_config"]["enabled"] = value.lower() in ("true", "1", "yes", "on")
        
        # String fields for dynthres parameters that are not numeric
        elif key_lower.startswith("dynthres_") and key_lower.endswith(("_mode", "_startpoint", "_measure", "_channels")):
            if "dynthres_config" not in params:
                params["dynthres_config"] = {}
            clean_key = key_lower[9:]  # Remove "dynthres_" prefix
            params["dynthres_config"][clean_key] = value
        elif key_lower == "dynthres_separate_feature_channels":
            if "dynthres_config" not in params:
                params["dynthres_config"] = {}
            params["dynthres_config"]["separate_feature_channels"] = value
        elif key_lower == "dynthres_variability_measure":
            if "dynthres_config" not in params:
                params["dynthres_config"] = {}
            params["dynthres_config"]["variability_measure"] = value
        elif key_lower == "dynthres_scaling_startpoint":
            if "dynthres_config" not in params:
                params["dynthres_config"] = {}
            params["dynthres_config"]["scaling_startpoint"] = value
        elif key_lower == "dynthres_mimic_mode":
            if "dynthres_config" not in params:
                params["dynthres_config"] = {}
            params["dynthres_config"]["mimic_mode"] = value
        elif key_lower == "dynthres_cfg_mode":
            if "dynthres_config" not in params:
                params["dynthres_config"] = {}
            params["dynthres_config"]["cfg_mode"] = value
            
        # Generic handling for any remaining dynthres parameters
        elif key_lower.startswith("dynthres_"):
            if "dynthres_config" not in params:
                params["dynthres_config"] = {}
            clean_key = key_lower[9:]  # Remove "dynthres_" prefix
            # Try to parse as number first, fall back to string
            try:
                if '.' in value:
                    params["dynthres_config"][clean_key] = float(value)
                else:
                    params["dynthres_config"][clean_key] = int(value)
            except ValueError:
                params["dynthres_config"][clean_key] = value
                
    except ValueError as e:
        logger.debug(f"Failed to convert parameter {key}={value}: {e}")
        # Store as string if conversion fails
        params[key_lower.replace(' ', '_')] = value
    except Exception as e:
        logger.debug(f"Error mapping parameter {key}={value}: {e}")
    
    return params


def extract_keywords_from_metadata(metadata: Dict[str, Any]) -> list[str]:
    """Extract searchable keywords from metadata."""
    keywords = []
    
    try:
        # From prompts
        if "prompt" in metadata and metadata["prompt"]:
            prompt_keywords = extract_keywords_from_prompt(metadata["prompt"])
            keywords.extend(prompt_keywords)
        
        # From model name
        if "model_name" in metadata and metadata["model_name"]:
            model_keywords = extract_keywords_from_model_name(metadata["model_name"])
            keywords.extend(model_keywords)
        
        # From file dimensions (aspect ratios)
        if "width" in metadata and "height" in metadata:
            aspect_keywords = get_aspect_ratio_keywords(metadata["width"], metadata["height"])
            keywords.extend(aspect_keywords)
            
    except Exception as e:
        logger.debug(f"Failed to extract keywords from metadata: {e}")
    
    return list(set(keywords))  # Remove duplicates


def extract_keywords_from_prompt(prompt: str) -> list[str]:
    """Extract keywords from a prompt string."""
    keywords = []
    
    # Simple keyword extraction - split on common delimiters
    # In a real implementation, you might use NLP libraries
    import re
    
    # Remove common prompt syntax
    prompt = re.sub(r'\([^)]*\)', '', prompt)  # Remove weight parentheses
    prompt = re.sub(r'\[[^\]]*\]', '', prompt)  # Remove negative brackets
    
    # Split and clean
    words = re.split(r'[,\s]+', prompt.lower())
    
    for word in words:
        word = word.strip('.,;:!?()[]{}"\'-')
        if len(word) > 2 and word.isalpha():  # Only alphabetic words > 2 chars
            keywords.append(word)
    
    return keywords[:20]  # Limit to first 20 keywords


def extract_keywords_from_model_name(model_name: str) -> list[str]:
    """Extract keywords from model name."""
    keywords = []
    
    # Common model name patterns
    if "sd15" in model_name.lower() or "1.5" in model_name:
        keywords.append("stable_diffusion_1_5")
    elif "sdxl" in model_name.lower():
        keywords.append("stable_diffusion_xl")
    elif "anime" in model_name.lower():
        keywords.append("anime")
    elif "realistic" in model_name.lower():
        keywords.append("realistic")
    
    return keywords


def get_aspect_ratio_keywords(width: int, height: int) -> list[str]:
    """Get aspect ratio keywords from dimensions."""
    keywords = []
    
    ratio = width / height
    
    if abs(ratio - 1.0) < 0.1:
        keywords.append("square")
    elif ratio > 1.5:
        keywords.append("landscape")
    elif ratio < 0.7:
        keywords.append("portrait")
    
    # Common resolutions
    if width == 512 and height == 512:
        keywords.append("512x512")
    elif width == 1024 and height == 1024:
        keywords.append("1024x1024")
    elif width == 1920 and height == 1080:
        keywords.append("1080p")
    
    return keywords