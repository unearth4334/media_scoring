"""Utility functions for reading PNG metadata and text chunks."""

import zlib
import re
from pathlib import Path
from typing import Optional, Dict, Any

from ..models.media_file import GenerationParameters


def read_png_parameters_text(png_path: Path, max_bytes: int = 2_000_000) -> Optional[str]:
    """
    Best-effort parse of PNG tEXt/zTXt/iTXt chunks to extract a 'parameters' text blob
    (e.g., Automatic1111 / ComfyUI). Returns the text payload if found; otherwise None.
    """
    try:
        with open(png_path, "rb") as f:
            sig = f.read(8)
            if sig != b"\x89PNG\r\n\x1a\n":
                return None
            read_total = 8
            param_text = None
            while True:
                if read_total > max_bytes:
                    break
                len_bytes = f.read(4)
                if len(len_bytes) < 4:
                    break
                length = int.from_bytes(len_bytes, "big")
                ctype = f.read(4)
                if len(ctype) < 4:
                    break
                data = f.read(length)
                if len(data) < length:
                    break
                _crc = f.read(4)
                read_total += 12 + length
                if ctype in (b"tEXt", b"zTXt", b"iTXt"):
                    try:
                        if ctype == b"tEXt":
                            # keyword\0text
                            if b"\x00" in data:
                                keyword, text = data.split(b"\x00", 1)
                                key = keyword.decode("latin-1", "ignore").strip().lower()
                                if key in ("parameters", "comment", "description"):
                                    t = text.decode("utf-8", "ignore").strip()
                                    if t:
                                        param_text = t
                        elif ctype == b"zTXt":
                            # keyword\0compression_method\0 compressed_text
                            if b"\x00" in data:
                                parts = data.split(b"\x00", 2)
                                if len(parts) >= 3:
                                    keyword = parts[0].decode("latin-1", "ignore").strip().lower()
                                    comp_method = parts[1][:1] if parts[1] else b"\x00"
                                    comp_data = parts[2]
                                    if comp_method == b"\x00":  # zlib/deflate
                                        try:
                                            txt = zlib.decompress(comp_data).decode("utf-8", "ignore").strip()
                                            if keyword in ("parameters", "comment", "description") and txt:
                                                param_text = txt
                                        except Exception:
                                            pass
                        elif ctype == b"iTXt":
                            # keyword\0 compression_flag\0 compression_method\0 language_tag\0 translated_keyword\0 text
                            # We handle only uncompressed (compression_flag==0)
                            parts = data.split(b'\x00', 5)
                            if len(parts) >= 6:
                                keyword = parts[0].decode("utf-8", "ignore").strip().lower()
                                comp_flag = parts[1][:1] if parts[1] else b"\x00"
                                # parts[2]=comp_method, parts[3]=language_tag, parts[4]=translated_keyword
                                text = parts[5]
                                if comp_flag == b"\x00":
                                    t = text.decode("utf-8", "ignore").strip()
                                    if keyword in ("parameters", "comment", "description") and t:
                                        param_text = t
                    except Exception:
                        pass
                if ctype == b"IEND":
                    break
            return param_text
    except Exception:
        return None


def parse_generation_parameters(param_text: str) -> GenerationParameters:
    """
    Parse generation parameters from PNG text metadata.
    
    Handles the format used by Automatic1111, ComfyUI, and similar tools.
    Example input text:
    "score_9, score_8_up, masterpiece, detailed, Steps: 20, Sampler: DPM++ 2M Karras, CFG scale: 7, Seed: 123456789, Size: 512x768, Model hash: abc123def, Model: mymodel_v1.0, Denoising strength: 0.75, Version: automatic1111 v1.6.0"
    """
    if not param_text:
        return GenerationParameters(raw_parameters=param_text)
    
    params = GenerationParameters(raw_parameters=param_text)
    
    # Split on commas but be careful about model names and other values that may contain commas
    # First, separate the prompt from the parameters (parameters usually start after "Steps:")
    param_lines = param_text.split('\n')
    
    # The first line(s) are usually the prompt, parameters come after
    param_section = ""
    for line in param_lines:
        if any(keyword in line for keyword in ["Steps:", "Sampler:", "CFG scale:", "Seed:", "Size:", "Model:"]):
            param_section += line + " "
    
    if not param_section:
        # Sometimes all parameters are on one line mixed with prompt
        param_section = param_text
    
    # Parse individual parameters using regex patterns
    patterns = {
        'steps': r'Steps:\s*(\d+)',
        'sampler': r'Sampler:\s*([^,\n]+?)(?:,|\n|$)',
        'schedule_type': r'Schedule\s*type:\s*([^,\n]+?)(?:,|\n|$)',
        'cfg_scale': r'CFG\s*scale:\s*([\d.]+)',
        'seed': r'Seed:\s*(\d+)',
        'size': r'Size:\s*(\d+x\d+)',
        'model_name': r'Model:\s*([^,\n]+?)(?:,|\n|$)',
        'model_hash': r'Model\s*hash:\s*([a-fA-F0-9]+)',
        'denoising_strength': r'Denoising\s*strength:\s*([\d.]+)',
        'hires_upscale': r'Hires\s*upscale:\s*([\d.]+)',
        'hires_upscaler': r'Hires\s*upscaler:\s*([^,\n]+?)(?:,|\n|$)',
        'hires_cfg_scale': r'Hires\s*CFG\s*scale:\s*([\d.]+)',
        'version': r'Version:\s*([^,\n]+?)(?:,|\n|$)',
        
        # Dynamic thresholding parameters
        'dynthres_enabled': r'Dynamic\s*thresholding\s*enabled:\s*(true|false)',
        'dynthres_mimic_scale': r'Mimic\s*scale:\s*([\d.]+)',
        'dynthres_threshold_percentile': r'Threshold\s*percentile:\s*([\d.]+)',
        'dynthres_mimic_mode': r'Mimic\s*mode:\s*([^,\n]+?)(?:,|\n|$)',
        'dynthres_mimic_scale_min': r'Mimic\s*scale\s*min:\s*([\d.]+)',
        'dynthres_cfg_mode': r'CFG\s*mode:\s*([^,\n]+?)(?:,|\n|$)',
        'dynthres_cfg_scale_min': r'CFG\s*scale\s*min:\s*([\d.]+)',
        'dynthres_sched_val': r'Sched\s*val:\s*([\d.]+)',
        'dynthres_separate_feature_channels': r'Separate\s*feature\s*channels:\s*(true|false)',
        'dynthres_scaling_startpoint': r'Scaling\s*startpoint:\s*([\d.]+)',
        'dynthres_variability_measure': r'Variability\s*measure:\s*([\d.]+)',
        'dynthres_interpolate_phi': r'Interpolate\s*phi:\s*([\d.]+)',
    }
    
    # Apply patterns to extract parameters
    for param_name, pattern in patterns.items():
        match = re.search(pattern, param_section, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            
            # Convert to appropriate type based on parameter
            try:
                if param_name in ['steps', 'seed']:
                    setattr(params, param_name, int(value))
                elif param_name in ['cfg_scale', 'denoising_strength', 'hires_upscale', 'hires_cfg_scale',
                                  'dynthres_mimic_scale', 'dynthres_threshold_percentile', 'dynthres_mimic_scale_min',
                                  'dynthres_cfg_scale_min', 'dynthres_sched_val', 'dynthres_scaling_startpoint',
                                  'dynthres_variability_measure', 'dynthres_interpolate_phi']:
                    setattr(params, param_name, float(value))
                elif param_name in ['dynthres_enabled', 'dynthres_separate_feature_channels']:
                    setattr(params, param_name, value.lower() == 'true')
                else:
                    # String parameters
                    setattr(params, param_name, value)
            except (ValueError, AttributeError):
                # If conversion fails, store as string or skip
                if hasattr(params, param_name):
                    setattr(params, param_name, value)
    
    # Special handling for some parameters that might have alternative formats
    
    # Look for "Hires Module 1" or similar
    hires_module_match = re.search(r'Hires\s*[Mm]odule\s*1:\s*([^,\n]+?)(?:,|\n|$)', param_section, re.IGNORECASE)
    if hires_module_match:
        params.hires_module_1 = hires_module_match.group(1).strip()
    
    # Some formats use different keywords, try alternatives
    if not params.sampler:
        # Try "Sampling method"
        sampler_match = re.search(r'Sampling\s*method:\s*([^,\n]+?)(?:,|\n|$)', param_section, re.IGNORECASE)
        if sampler_match:
            params.sampler = sampler_match.group(1).strip()
    
    if not params.model_name:
        # Try "Model name"
        model_match = re.search(r'Model\s*name:\s*([^,\n]+?)(?:,|\n|$)', param_section, re.IGNORECASE)
        if model_match:
            params.model_name = model_match.group(1).strip()
    
    return params


def extract_png_metadata(png_path: Path) -> Optional[GenerationParameters]:
    """
    Extract full generation metadata from a PNG file.
    
    Returns GenerationParameters object if metadata is found, None otherwise.
    """
    param_text = read_png_parameters_text(png_path)
    if param_text:
        return parse_generation_parameters(param_text)
    return None