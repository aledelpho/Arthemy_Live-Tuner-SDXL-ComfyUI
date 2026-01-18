import comfy.sd
import torch
import re

class ArthemyClipLiveTunerSDXL:
    """
    Arthemy CLIP Tuner (SDXL)
    
    This node modulates the weights of the SDXL CLIP model (OpenCLIP ViT-bigG)
    by dividing the 32 layers into three semantic bands: Syntax, Semantics, and Style.
    It enables precise control over how the text encoder interprets the prompt 
    at different levels of abstraction.
    """
    
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "clip": ("CLIP",),
                "mode": (["Soft Value", "Real Value"],),
                "base_scale": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.01, "tooltip": "Global multiplier applied to all layers."}),
                
                # Band 1: Early Layers (~0-35%)
                "syntax_rigidity": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.01, "tooltip": "Controls grammar parsing and token strictness (Early Layers)."}),
                
                # Band 2: Middle Layers (~35-75%)
                "semantic_focus": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.01, "tooltip": "Controls subject recognition and action attributes (Middle Layers)."}),
                
                # Band 3: Late Layers (~75-100%)
                "style_abstraction": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.01, "tooltip": "Controls global composition and artistic interpretation (Late Layers)."}),
            }
        }

    RETURN_TYPES = ("CLIP", "STRING", )
    RETURN_NAMES = ("CLIP", "info", )
    FUNCTION = "tune_clip"
    CATEGORY = "Arthemy/SDXL"

    def tune_clip(self, clip, mode, base_scale, syntax_rigidity, semantic_focus, style_abstraction):
        
        def get_target_weight(w):
            if mode == "Real Value": 
                return w
            # Soft Value: Scaled range (0.8 to 1.2) for safer modulation
            return 0.8 + (0.2 * w)

        # Layer Segmentation Configuration
        # Defines the normalized depth (0.0 - 1.0) where transitions occur.
        BLOCK_BOUNDARIES = {
            "syntax_end": 0.35,   # 0% - 35%
            "semantic_end": 0.75  # 35% - 75%
            # Style > 75%
        }

        # Calculate target weights
        w_base = get_target_weight(base_scale)
        w_syntax = get_target_weight(syntax_rigidity)
        w_semantic = get_target_weight(semantic_focus)
        w_style = get_target_weight(style_abstraction)

        clip_out = clip.clone()
        kp = clip_out.get_key_patches()
        
        active_patches = 0
        TOTAL_LAYERS_SDXL = 32 # SDXL uses OpenCLIP-ViT-bigG

        for key in kp:
            # Skip non-layer specific keys
            if key.endswith(".position_ids") or key.endswith(".logit_scale"):
                continue

            target_scale = w_base

            # Identify layer index and determine band
            match = re.search(r"\.layers\.(\d+)\.", key)
            if match:
                idx = int(match.group(1))
                ratio = idx / TOTAL_LAYERS_SDXL
                
                if ratio <= BLOCK_BOUNDARIES["syntax_end"]:
                    target_scale = w_syntax
                elif ratio <= BLOCK_BOUNDARIES["semantic_end"]:
                    target_scale = w_semantic
                else:
                    target_scale = w_style

            # Apply weight modification
            strength = target_scale - 1.0
            if strength != 0:
                clip_out.add_patches({key: kp[key]}, strength, 1.0)
                active_patches += 1

        info = f"CLIP Tuned | Syn: {w_syntax:.2f} | Sem: {w_semantic:.2f} | Sty: {w_style:.2f}"
        return (clip_out, info, )

NODE_CLASS_MAPPINGS = {"ArthemyClipLiveTunerSDXL": ArthemyClipLiveTunerSDXL}
NODE_DISPLAY_NAME_MAPPINGS = {"ArthemyClipLiveTunerSDXL": "✨ Arthemy CLIP Tuner (SDXL)"}