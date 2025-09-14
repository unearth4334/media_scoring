"""Parser for prompt text to extract keywords with attention weights and LoRAs."""

import re
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class Keyword:
    """Represents a keyword with its attention weight."""
    text: str
    weight: float

    def __str__(self):
        return f"{self.text}:{self.weight:.2f}"


@dataclass
class LoRA:
    """Represents a LoRA with its weight."""
    name: str
    weight: float

    def __str__(self):
        return f"<lora:{self.name}:{self.weight}>"


@dataclass
class ParsedPrompt:
    """Represents a parsed prompt with keywords and LoRAs."""
    positive_keywords: List[Keyword]
    negative_keywords: List[Keyword]
    loras: List[LoRA]
    raw_positive: str
    raw_negative: str


class PromptParser:
    """Parser for AI prompt text with attention weight syntax."""
    
    def __init__(self):
        # Regex pattern for LoRA syntax: <lora:name:weight>
        self.lora_pattern = re.compile(r'<lora:([^:>]+):([0-9.]+)>')
        
    def parse_png_text(self, png_text: str) -> ParsedPrompt:
        """
        Parse PNG text to extract positive/negative prompts, keywords, and LoRAs.
        
        Args:
            png_text: Raw PNG text content containing prompts
            
        Returns:
            ParsedPrompt object with extracted keywords and LoRAs
        """
        # Split into positive and negative prompts
        positive_text, negative_text = self._split_prompts(png_text)
        
        # Extract LoRAs from both parts (but mainly from positive)
        loras = self._extract_loras(png_text)
        
        # Clean text by removing LoRAs for keyword extraction
        clean_positive = self._remove_loras(positive_text)
        clean_negative = self._remove_loras(negative_text)
        
        # Parse keywords with attention weights
        positive_keywords = self._parse_keywords(clean_positive)
        negative_keywords = self._parse_keywords(clean_negative)
        
        return ParsedPrompt(
            positive_keywords=positive_keywords,
            negative_keywords=negative_keywords,
            loras=loras,
            raw_positive=positive_text.strip(),
            raw_negative=negative_text.strip()
        )
    
    def _split_prompts(self, text: str) -> Tuple[str, str]:
        """Split text into positive and negative prompts."""
        # Look for "Negative prompt:" delimiter
        negative_match = re.search(r'Negative prompt:\s*(.*?)(?:\n[A-Z][a-z]+:|$)', text, re.DOTALL | re.IGNORECASE)
        
        if negative_match:
            # Find where negative prompt starts
            negative_start = negative_match.start()
            positive_text = text[:negative_start].strip()
            negative_text = negative_match.group(1).strip()
        else:
            positive_text = text.strip()
            negative_text = ""
        
        return positive_text, negative_text
    
    def _extract_loras(self, text: str) -> List[LoRA]:
        """Extract LoRA calls from text."""
        loras = []
        
        for match in self.lora_pattern.finditer(text):
            name = match.group(1)
            try:
                weight = float(match.group(2))
                loras.append(LoRA(name=name, weight=weight))
            except ValueError:
                # Skip invalid weight values
                continue
        
        return loras
    
    def _remove_loras(self, text: str) -> str:
        """Remove LoRA calls from text."""
        return self.lora_pattern.sub('', text).strip()
    
    def _parse_keywords(self, text: str) -> List[Keyword]:
        """Parse keywords from text, calculating attention weights."""
        if not text.strip():
            return []
        
        keywords = []
        
        # Split by commas and process each potential keyword
        parts = [part.strip() for part in text.split(',') if part.strip()]
        
        for part in parts:
            # Skip technical parameters (Steps, Sampler, etc.)
            if self._is_technical_parameter(part):
                continue
                
            keyword = self._parse_single_keyword(part)
            if keyword:
                keywords.append(keyword)
        
        return keywords
    
    def _is_technical_parameter(self, text: str) -> bool:
        """Check if text is a technical parameter rather than a keyword."""
        technical_patterns = [
            r'^Steps:\s*\d+',
            r'^Sampler:\s*',
            r'^Schedule type:\s*',
            r'^CFG scale:\s*',
            r'^Seed:\s*',
            r'^Size:\s*',
            r'^Model hash:\s*',
            r'^Model:\s*',
            r'^Lora hashes:\s*',
            r'^Version:\s*',
            r'^\w+_enabled:\s*',
            r'^\w+_\w+:\s*\d',
        ]
        
        for pattern in technical_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        return False
    
    def _parse_single_keyword(self, text: str) -> Optional[Keyword]:
        """Parse a single keyword with attention weight syntax."""
        if not text.strip():
            return None
        
        # Calculate attention weight from parentheses and brackets
        weight, clean_text = self._calculate_attention_weight(text)
        
        # Clean up the keyword text
        clean_text = clean_text.strip()
        if not clean_text:
            return None
        
        # Skip empty keywords or very short non-meaningful ones
        if len(clean_text) < 2 or clean_text.isdigit():
            return None
        
        return Keyword(text=clean_text, weight=weight)
    
    def _calculate_attention_weight(self, text: str) -> Tuple[float, str]:
        """
        Calculate attention weight from parentheses/brackets syntax.
        
        Rules:
        - Each () increases weight by 1.1x
        - Each [] decreases weight by ~0.907x  
        - (word:1.5) sets specific weight
        - Multiple levels multiply: ((word)) = 1.1 * 1.1 = 1.21
        """
        original_text = text.strip()
        weight = 1.0
        
        # Handle specific weight syntax: (word:1.5)
        specific_weight_match = re.search(r'\(([^:)]+):([0-9.]+)\)', original_text)
        if specific_weight_match:
            try:
                weight = float(specific_weight_match.group(2))
                clean_text = specific_weight_match.group(1).strip()
                return weight, clean_text
            except ValueError:
                pass
        
        # Count parentheses and brackets from outside to inside
        clean_text = original_text
        
        # Count matched parentheses pairs for emphasis
        paren_count = 0
        while (clean_text.startswith('(') and clean_text.endswith(')')):
            # Check if this is a valid pair by ensuring balanced parentheses
            inner_text = clean_text[1:-1]
            if self._is_balanced_parentheses(inner_text):
                paren_count += 1
                clean_text = inner_text
            else:
                break
        
        # Apply emphasis multiplier
        weight *= (1.1 ** paren_count)
        
        # Count matched bracket pairs for de-emphasis
        bracket_count = 0
        while (clean_text.startswith('[') and clean_text.endswith(']')):
            # Check if this is a valid pair by ensuring balanced brackets
            inner_text = clean_text[1:-1]
            if self._is_balanced_brackets(inner_text):
                bracket_count += 1
                clean_text = inner_text
            else:
                break
        
        # Apply de-emphasis multiplier
        weight *= (0.907 ** bracket_count)
        
        return weight, clean_text.strip()
    
    def _is_balanced_parentheses(self, text: str) -> bool:
        """Check if parentheses are balanced in text (for proper nesting)."""
        count = 0
        for char in text:
            if char == '(':
                count += 1
            elif char == ')':
                count -= 1
                if count < 0:
                    return False
        return count == 0
    
    def _is_balanced_brackets(self, text: str) -> bool:
        """Check if brackets are balanced in text (for proper nesting)."""
        count = 0
        for char in text:
            if char == '[':
                count += 1
            elif char == ']':
                count -= 1
                if count < 0:
                    return False
        return count == 0


def parse_png_prompt_text(png_text: str) -> ParsedPrompt:
    """
    Convenience function to parse PNG prompt text.
    
    Args:
        png_text: Raw PNG text content
        
    Returns:
        ParsedPrompt with extracted keywords and LoRAs
    """
    parser = PromptParser()
    return parser.parse_png_text(png_text)