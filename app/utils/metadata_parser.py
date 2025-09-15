"""Utility functions for parsing generation metadata from PNG parameter text."""

import re
from typing import Dict, Any, Optional


def parse_generation_metadata(parameter_text: str) -> Dict[str, Any]:
    """
    Parse generation metadata from PNG parameter text.
    
    Expected format from issue example:
    score_9, score_8_up, ..., prompt_text
    
    Also looks for standard generation parameters like:
    Steps: 20, Sampler: DPM++ 2M Karras, CFG scale: 7, etc.
    
    Returns dict with parsed metadata fields.
    """
    if not parameter_text:
        return {}
    
    metadata = {}
    
    # Split by lines and commas to find key-value pairs
    lines = parameter_text.split('\n')
    all_text = parameter_text.replace('\n', ', ')
    
    # Common patterns for generation parameters
    patterns = {
        'steps': r'Steps:\s*(\d+)',
        'sampler': r'Sampler:\s*([^,\n]+)',
        'schedule_type': r'Schedule type:\s*([^,\n]+)',
        'cfg_scale': r'CFG scale:\s*([\d.]+)',
        'seed': r'Seed:\s*(\d+)',
        'size': r'Size:\s*(\d+x\d+)',
        'model': r'Model:\s*([^,\n]+)',
        'model_hash': r'Model hash:\s*([a-fA-F0-9]+)',
        'denoising_strength': r'Denoising strength:\s*([\d.]+)',
        'hires_upscale': r'Hires upscale:\s*([\d.]+)',
        'hires_upscaler': r'Hires upscaler:\s*([^,\n]+)',
        'hires_cfg_scale': r'Hires CFG Scale:\s*([\d.]+)',
        'version': r'Version:\s*([^,\n]+)',
    }
    
    # Dynamic thresholding patterns
    dynthresh_patterns = {
        'dynthres_enabled': r'dynthres_enabled:\s*(true|false)',
        'dynthres_mimic_scale': r'dynthres_mimic_scale:\s*([\d.]+)',
        'dynthres_threshold_percentile': r'dynthres_threshold_percentile:\s*([\d.]+)',
        'dynthres_mimic_mode': r'dynthres_mimic_mode:\s*([^,\n]+)',
        'dynthres_mimic_scale_min': r'dynthres_mimic_scale_min:\s*([\d.]+)',
        'dynthres_cfg_mode': r'dynthres_cfg_mode:\s*([^,\n]+)',
        'dynthres_cfg_scale_min': r'dynthres_cfg_scale_min:\s*([\d.]+)',
        'dynthres_sched_val': r'dynthres_sched_val:\s*([\d.]+)',
        'dynthres_separate_feature_channels': r'dynthres_separate_feature_channels:\s*(true|false)',
        'dynthres_scaling_startpoint': r'dynthres_scaling_startpoint:\s*([\d.]+)',
        'dynthres_variability_measure': r'dynthres_variability_measure:\s*([\d.]+)',
        'dynthres_interpolate_phi': r'dynthres_interpolate_phi:\s*([\d.]+)',
    }
    
    # Combine all patterns
    all_patterns = {**patterns, **dynthresh_patterns}
    
    # Extract values using regex patterns
    for key, pattern in all_patterns.items():
        match = re.search(pattern, all_text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            
            # Convert specific types
            if key in ['steps', 'seed']:
                try:
                    metadata[key] = int(value)
                except ValueError:
                    metadata[key] = value
            elif key in ['cfg_scale', 'denoising_strength', 'hires_upscale', 'hires_cfg_scale',
                        'dynthres_mimic_scale', 'dynthres_threshold_percentile', 
                        'dynthres_mimic_scale_min', 'dynthres_cfg_scale_min',
                        'dynthres_sched_val', 'dynthres_scaling_startpoint',
                        'dynthres_variability_measure', 'dynthres_interpolate_phi']:
                try:
                    metadata[key] = float(value)
                except ValueError:
                    metadata[key] = value
            elif key in ['dynthres_enabled', 'dynthres_separate_feature_channels']:
                metadata[key] = value.lower() == 'true'
            else:
                metadata[key] = value
    
    # Extract model info if found
    if 'model' in metadata:
        model_text = metadata['model']
        # Try to extract model name and hash if in format "name [hash]"
        model_match = re.match(r'^([^[]+)(?:\s*\[([a-fA-F0-9]+)\])?', model_text)
        if model_match:
            model_name = model_match.group(1).strip()
            model_hash = model_match.group(2) or metadata.get('model_hash', '')
            metadata['model'] = {
                'name': model_name,
                'hash': model_hash
            }
    
    # Store the full parameter text as well
    metadata['full_parameters'] = parameter_text
    
    return metadata