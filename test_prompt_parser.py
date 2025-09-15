#!/usr/bin/env python3
"""
Test script for the prompt parser functionality.
"""

import sys
from pathlib import Path

# Add the parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app.utils.prompt_parser import PromptParser, parse_png_prompt_text


def test_with_example_text():
    """Test the parser with the example text from the problem statement."""
    
    example_text = """score_9, score_8_up, score_7_up, masterpiece, high quality, realistic, cinematic, detailed face, detailed eyes, calm, perfect eyes, warm colors, (((light pink))), bokeh, abstract background, ethereal background, bright subject,
1girl, alone, city, playful, 18yo, cute, Asian girl, cat eat headband, short girl, adorable, round face, BREAK, silver hair, straight hair, short hair, styled hair, tied hair, (mad-wsps:0.6), BREAK, perfect eyes, eyes, dimples, blush, perfect eyes, ((transparent)), body, on the bed, legs, puffy, medium breasts, provocative, earrings, thigh high stockings, glowing, luminous outlines, radiant contours tracing, [swirling light], and wrinkles of fabric, clothing glowing light, invisible, luminous, radiant highlights, shimmering (light traces:1.2), glowing energy-style fashion, neon glow effect, futuristic, surreal luminous,
defined only by glowing contours, outlined vector graphics, glowing fumes, electric flames, glimmering accents, luminous, rainbow, neon, (mad-wsps:0.8)
<lora:zy_Realism_Enhancer_v2:0.9>
<lora:Dramatic Lighting Slider-mid_1105685-vid_1242203:1.2>
<lora:Kawaii_PastelCore_v1_xxXL-mid_1702738-vid_1926995:1.5>
<lora:Wisps_of_Light_Pony:0.7>
<lora:RealSkin_xxXL_v1-mid_1486921-vid_1681921:2.2>
<lora:Add_color_PDXLv1-mid_1327644-vid_1498957:1>
Negative prompt: zPDXL3-mid_332646-vid_720175, CyberRealistic_Negative_PONY-neg-mid_1531977-vid_972770, score_5, score_4, 3d, simple background, (angular face:1.3), pointy chin, flat chested, old, muscular, scowl, moles, bare chest, naked, nipples, (hands:1.2), makeup, pointy chin, skinny, overexposed, garden, forest, fabric, dark, pendant, circles, tentacles, feather, intricate, symmetry, (bra:1.5), glasses, dumb
Steps: 30, Sampler: DPM++ 3M SDE, Schedule type: Karras, CFG scale: 5, Seed: 2480865251, Size: 1152x896, Model hash: c379d154eb, Model: albedobaseXL_v31Large-mid_140737-vid_1041855, Lora hashes: "zy_Realism_Enhancer_v2: b46384abcc66, Dramatic Lighting Slider-mid_1105685-vid_1242203: cad8e9106645, Kawaii_PastelCore_v1_xxXL-mid_1702738-vid_1926995: 2ba55606f88b, Wisps_of_Light_Pony: 95011c7288d0, RealSkin_xxXL_v1-mid_1486921-vid_1681921: 229fd1d9a157, Add_color_PDXLv1-mid_1327644-vid_1498957: bc21d926bade", dynthres_enabled: True, dynthres_mimic_scale: 7, dynthres_threshold_percentile: 1, dynthres_mimic_mode: Linear Down, dynthres_mimic_scale_min: 0, dynthres_cfg_mode: Constant, dynthres_cfg_scale_min: 0, dynthres_sched_val: 1, dynthres_separate_feature_channels: enable, dynthres_scaling_startpoint: MEAN, dynthres_variability_measure: AD, dynthres_interpolate_phi: 1, Version: f2.0.1v1.10.1-previous-669-gdfdcbab6"""
    
    print("Testing prompt parser with example text...")
    print("=" * 80)
    
    # Parse the text
    result = parse_png_prompt_text(example_text)
    
    # Display results
    print(f"Raw positive prompt: {result.raw_positive[:100]}...")
    print(f"Raw negative prompt: {result.raw_negative[:100]}...")
    print()
    
    print(f"Found {len(result.positive_keywords)} positive keywords:")
    for i, kw in enumerate(result.positive_keywords[:10]):  # Show first 10
        print(f"  {i+1:2}. {kw}")
    if len(result.positive_keywords) > 10:
        print(f"  ... and {len(result.positive_keywords) - 10} more")
    print()
    
    print(f"Found {len(result.negative_keywords)} negative keywords:")
    for i, kw in enumerate(result.negative_keywords[:10]):  # Show first 10
        print(f"  {i+1:2}. {kw}")
    if len(result.negative_keywords) > 10:
        print(f"  ... and {len(result.negative_keywords) - 10} more")
    print()
    
    print(f"Found {len(result.loras)} LoRAs:")
    for i, lora in enumerate(result.loras):
        print(f"  {i+1}. {lora}")
    print()
    
    # Test specific examples mentioned in the problem statement
    print("Testing specific attention weight examples:")
    print("-" * 40)
    
    # Test (((light pink))) should be 1.1^3 = 1.331
    light_pink_kw = next((kw for kw in result.positive_keywords if "light pink" in kw.text), None)
    if light_pink_kw:
        print(f"(((light pink))) -> {light_pink_kw.text}: {light_pink_kw.weight:.2f} (expected ~1.33)")
    
    # Test [swirling light] should be 0.907
    swirling_kw = next((kw for kw in result.positive_keywords if "swirling light" in kw.text), None)
    if swirling_kw:
        print(f"[swirling light] -> {swirling_kw.text}: {swirling_kw.weight:.2f} (expected ~0.91)")
    
    # Test (mad-wsps:0.6) should be exactly 0.6
    mad_wsps_kw = next((kw for kw in result.positive_keywords if "mad-wsps" in kw.text), None)
    if mad_wsps_kw:
        print(f"(mad-wsps:0.6) -> {mad_wsps_kw.text}: {mad_wsps_kw.weight:.2f} (expected 0.60)")
    
    # Test (light traces:1.2) should be exactly 1.2  
    light_traces_kw = next((kw for kw in result.positive_keywords if "light traces" in kw.text), None)
    if light_traces_kw:
        print(f"(light traces:1.2) -> {light_traces_kw.text}: {light_traces_kw.weight:.2f} (expected 1.20)")
    
    # Test ((transparent)) should be 1.1^2 = 1.21
    transparent_kw = next((kw for kw in result.positive_keywords if "transparent" in kw.text), None)
    if transparent_kw:
        print(f"((transparent)) -> {transparent_kw.text}: {transparent_kw.weight:.2f} (expected ~1.21)")
    
    print()
    print("Test completed!")
    return result


def test_edge_cases():
    """Test various edge cases for the parser."""
    print("Testing edge cases...")
    print("=" * 80)
    
    parser = PromptParser()
    
    # Test nested parentheses
    test_cases = [
        ("simple keyword", 1.0),
        ("(emphasized)", 1.1), 
        ("((double emphasis))", 1.21),
        ("(((triple emphasis)))", 1.331),
        ("[deemphasized]", 0.907),
        ("[[double deemphasis]]", 0.822),
        ("(specific weight:2.5)", 2.5),
        ("(another:0.1)", 0.1),
        ("", None),  # Empty should return None
        ("  whitespace  ", 1.0),  # Should handle whitespace
    ]
    
    for text, expected_weight in test_cases:
        if expected_weight is None:
            keyword = parser._parse_single_keyword(text)
            print(f"'{text}' -> None (expected)")
        else:
            keyword = parser._parse_single_keyword(text)
            if keyword:
                print(f"'{text}' -> {keyword.text}: {keyword.weight:.2f} (expected {expected_weight:.2f})")
            else:
                print(f"'{text}' -> None (unexpected)")
    
    print("Edge case testing completed!")


if __name__ == "__main__":
    print("Prompt Parser Test Suite")
    print("=" * 80)
    
    # Test with the provided example
    test_with_example_text()
    print()
    
    # Test edge cases
    test_edge_cases()