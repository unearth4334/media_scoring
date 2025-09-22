#!/usr/bin/env python3
"""
Integration test for prompt parsing in the full pipeline.
"""

import sys
import tempfile
import json
import os
from pathlib import Path

# Add the parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app.utils.prompt_parser import parse_png_prompt_text
from app.services.metadata import extract_metadata, parse_ai_parameters
from app.database.engine import init_database
from app.database.service import DatabaseService


def create_test_png_with_metadata():
    """Create a test PNG file with AI metadata."""
    # For this test, we'll simulate PNG text extraction
    # In reality, this would come from actual PNG chunks
    example_png_text = """score_9, score_8_up, score_7_up, masterpiece, high quality, realistic, cinematic, detailed face, detailed eyes, calm, perfect eyes, warm colors, (((light pink))), bokeh, abstract background, ethereal background, bright subject,
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
    
    return example_png_text


def test_parse_ai_parameters():
    """Test the parse_ai_parameters function directly."""
    print("Testing parse_ai_parameters function...")
    print("=" * 60)
    
    png_text = create_test_png_with_metadata()
    
    # Test the AI parameters parsing
    ai_params = parse_ai_parameters(png_text)
    
    print(f"Extracted prompt: {ai_params.get('prompt', 'N/A')[:100]}...")
    print(f"Extracted negative prompt: {ai_params.get('negative_prompt', 'N/A')[:100]}...")
    print()
    
    # Check if parsed_prompt_data is present
    if 'parsed_prompt_data' in ai_params:
        prompt_data = ai_params['parsed_prompt_data']
        
        print(f"Positive keywords: {len(prompt_data['positive_keywords'])}")
        for i, kw in enumerate(prompt_data['positive_keywords'][:5]):
            print(f"  {i+1}. {kw.text}: {kw.weight:.2f}")
        if len(prompt_data['positive_keywords']) > 5:
            print(f"  ... and {len(prompt_data['positive_keywords']) - 5} more")
        print()
        
        print(f"Negative keywords: {len(prompt_data['negative_keywords'])}")
        for i, kw in enumerate(prompt_data['negative_keywords'][:5]):
            print(f"  {i+1}. {kw.text}: {kw.weight:.2f}")
        if len(prompt_data['negative_keywords']) > 5:
            print(f"  ... and {len(prompt_data['negative_keywords']) - 5} more")
        print()
        
        print(f"LoRAs: {len(prompt_data['loras'])}")
        for i, lora in enumerate(prompt_data['loras']):
            print(f"  {i+1}. {lora.name}: {lora.weight}")
        print()
        
        # Test specific attention weights
        print("Verifying attention weight calculations:")
        light_pink = next((kw for kw in prompt_data['positive_keywords'] if 'light pink' in kw.text), None)
        if light_pink:
            print(f"  (((light pink))) -> {light_pink.weight:.2f} (expected ~1.33)")
        
        transparent = next((kw for kw in prompt_data['positive_keywords'] if 'transparent' in kw.text), None)  
        if transparent:
            print(f"  ((transparent)) -> {transparent.weight:.2f} (expected ~1.21)")
        
        swirling = next((kw for kw in prompt_data['positive_keywords'] if 'swirling light' in kw.text), None)
        if swirling:
            print(f"  [swirling light] -> {swirling.weight:.2f} (expected ~0.91)")
        
        mad_wsps = next((kw for kw in prompt_data['positive_keywords'] if 'mad-wsps' in kw.text), None)
        if mad_wsps:
            print(f"  (mad-wsps:0.6) -> {mad_wsps.weight:.2f} (expected 0.60)")
        
        print("✅ parse_ai_parameters test completed!")
    else:
        print("❌ No parsed_prompt_data found!")
    
    return ai_params


def test_database_storage():
    """Test storing the parsed data in the database (requires PostgreSQL DATABASE_URL).""" 
    print("\nTesting database storage...")
    print("=" * 60)
    
    # Check if DATABASE_URL is set
    db_url = os.getenv('DATABASE_URL')
    if not db_url or not db_url.startswith('postgresql://'):
        print("⏭️  Database storage test skipped (no PostgreSQL DATABASE_URL set)")
        return
    
    # Initialize database
    with tempfile.TemporaryDirectory() as temp_dir:
        database_url = db_url
        
        print(f"Initializing test database: {database_url}")
        init_database(database_url)
        
        # Create test metadata
        png_text = create_test_png_with_metadata()
        ai_params = parse_ai_parameters(png_text)
        
        # Create a real temporary file for testing
        temp_file = Path(temp_dir) / "test_image.png"
        temp_file.write_bytes(b"fake PNG data")  # Create a minimal file
        
        # Store metadata in database
        with DatabaseService() as db:
            metadata_obj = db.store_media_metadata(temp_file, ai_params)
            
            print(f"Stored metadata for: {temp_file}")
            print(f"Prompt: {metadata_obj.prompt[:100] if metadata_obj.prompt else 'None'}...")
            print(f"Negative prompt: {metadata_obj.negative_prompt[:100] if metadata_obj.negative_prompt else 'None'}...")
            
            # Check if the JSON fields are stored correctly
            if metadata_obj.positive_prompt_keywords:
                print(f"Positive keywords stored: {len(metadata_obj.positive_prompt_keywords)} entries")
                for i, kw_dict in enumerate(metadata_obj.positive_prompt_keywords[:3]):
                    print(f"  {i+1}. {kw_dict['text']}: {kw_dict['weight']:.2f}")
                if len(metadata_obj.positive_prompt_keywords) > 3:
                    print(f"  ... and {len(metadata_obj.positive_prompt_keywords) - 3} more")
            
            if metadata_obj.negative_prompt_keywords:
                print(f"Negative keywords stored: {len(metadata_obj.negative_prompt_keywords)} entries")
                
            if metadata_obj.loras:
                print(f"LoRAs stored: {len(metadata_obj.loras)} entries")
                for i, lora_dict in enumerate(metadata_obj.loras):
                    print(f"  {i+1}. {lora_dict['name']}: {lora_dict['weight']}")
            
            print("✅ Database storage test completed!")
            
            # Verify we can retrieve the data
            retrieved = db.get_media_metadata(temp_file)
            if retrieved and retrieved.positive_prompt_keywords:
                print("✅ Data retrieval confirmed!")
                return True
            else:
                print("❌ Failed to retrieve stored data!")
                return False


def main():
    """Run all integration tests."""
    print("Full Integration Test for PNG Prompt Parser")
    print("=" * 80)
    
    try:
        # Test 1: Parse AI parameters
        ai_params = test_parse_ai_parameters()
        
        # Test 2: Database storage
        success = test_database_storage()
        
        if success:
            print("\n🎉 All integration tests passed!")
        else:
            print("\n❌ Some tests failed!")
            
    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()