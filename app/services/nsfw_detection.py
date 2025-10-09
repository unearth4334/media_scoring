"""NSFW Detection Service using Marqo/nsfw-image-detection-384 model."""

import logging
from pathlib import Path
from typing import Tuple, Optional
import tempfile
import os

logger = logging.getLogger(__name__)

try:
    import timm
    import torch
    from PIL import Image
    NSFW_DETECTION_AVAILABLE = True
except ImportError as e:
    logger.warning(f"NSFW detection dependencies not available: {e}")
    NSFW_DETECTION_AVAILABLE = False


class NSFWDetector:
    """NSFW detection using Marqo/nsfw-image-detection-384 model."""
    
    def __init__(self):
        self.model = None
        self.transforms = None
        self.class_names = None
        self._initialized = False
        
    def _initialize_model(self):
        """Initialize the NSFW detection model."""
        if self._initialized or not NSFW_DETECTION_AVAILABLE:
            return
            
        try:
            logger.info("Loading NSFW detection model: Marqo/nsfw-image-detection-384")
            
            # Load the model
            self.model = timm.create_model("hf_hub:Marqo/nsfw-image-detection-384", pretrained=True)
            self.model = self.model.eval()
            
            # Get data configuration and transforms
            data_config = timm.data.resolve_model_data_config(self.model)
            self.transforms = timm.data.create_transform(**data_config, is_training=False)
            
            # Get class names
            self.class_names = self.model.pretrained_cfg["label_names"]
            
            self._initialized = True
            logger.info(f"NSFW detection model loaded successfully. Classes: {self.class_names}")
            
        except Exception as e:
            logger.error(f"Failed to initialize NSFW detection model: {e}")
            self._initialized = False
            
    def detect_nsfw(self, image_path: Path) -> Tuple[Optional[float], Optional[str]]:
        """
        Detect NSFW content in an image.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Tuple of (nsfw_score, nsfw_label) where:
            - nsfw_score: Probability of NSFW content (0.0-1.0)
            - nsfw_label: 'sfw' or 'nsfw'
            Returns (None, None) if detection fails or is unavailable
        """
        if not NSFW_DETECTION_AVAILABLE:
            logger.debug("NSFW detection not available (missing dependencies)")
            return None, None
            
        if not self._initialized:
            self._initialize_model()
            
        if not self._initialized:
            return None, None
            
        try:
            # Load and process image
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                    
                # Apply transforms
                input_tensor = self.transforms(img).unsqueeze(0)
                
                # Run inference
                with torch.no_grad():
                    output = self.model(input_tensor).softmax(dim=-1).cpu()
                    
                # Get probabilities
                probabilities = output[0].numpy()
                predicted_class_idx = output[0].argmax().item()
                predicted_class = self.class_names[predicted_class_idx]
                
                # Assuming class_names are ['sfw', 'nsfw'] or similar
                if len(probabilities) == 2:
                    # Get NSFW probability (assuming index 1 is NSFW)
                    nsfw_prob = float(probabilities[1] if self.class_names[1].lower() == 'nsfw' else probabilities[0])
                    nsfw_label = 'nsfw' if nsfw_prob > 0.5 else 'sfw'
                else:
                    # Fallback
                    nsfw_prob = float(probabilities[predicted_class_idx])
                    nsfw_label = predicted_class.lower()
                    
                logger.debug(f"NSFW detection for {image_path.name}: {nsfw_label} ({nsfw_prob:.3f})")
                return nsfw_prob, nsfw_label
                
        except Exception as e:
            logger.error(f"Error during NSFW detection for {image_path}: {e}")
            return None, None
            
    def is_available(self) -> bool:
        """Check if NSFW detection is available."""
        return NSFW_DETECTION_AVAILABLE
        
        
# Global instance
nsfw_detector = NSFWDetector()


def detect_image_nsfw(image_path: Path) -> Tuple[Optional[float], Optional[str]]:
    """
    Convenience function to detect NSFW content in an image.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Tuple of (nsfw_score, nsfw_label)
    """
    return nsfw_detector.detect_nsfw(image_path)


def is_nsfw_detection_available() -> bool:
    """Check if NSFW detection is available."""
    return nsfw_detector.is_available()