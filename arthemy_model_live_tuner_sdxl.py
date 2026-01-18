import comfy.sd
import torch
import re

class ArthemyLiveModelTunerSDXL:
    """
    Arthemy Model Tuner (SDXL)
    
    This node modulates the weights of the SDXL UNet model by scaling specific 
    block groups. It allows for granular control over generation aspects by 
    targeting specific semantic sections of the architecture (Input, Middle, Output).
    """
    
    # Mapping of logical groups to internal SDXL Block Indices.
    # Total SDXL Blocks: 19 (9 Input, 1 Middle, 9 Output).
    GROUP_MAP = {
        # --- INPUT BLOCKS: Structure & Composition ---
        "IN_Layout_Geometry": [0, 1],       # Spatial features and high-res layout
        "IN_Perspective_Masses": [2, 3],    # Global shapes and perspective
        "IN_Subject_Identity": [4, 5],      # Object semantics and structure
        "IN_Global_Composition": [6, 7, 8], # High-level semantic arrangement
        
        # --- MIDDLE BLOCK: Core ---
        "MID_Core_Concept": [9],            # Central semantic processing
        
        # --- OUTPUT BLOCKS: Style & Rendering ---
        "OUT_Art_Style_Medium": [10, 11],   # Artistic style and medium definition
        "OUT_Material_Substance": [12],     # Material properties
        "OUT_Lighting_Atmosphere": [13, 14],# Volumetric lighting and atmosphere
        "OUT_Shadows_Depth": [15],          # Contrast and depth perception
        "OUT_Texture_Details": [16, 17],    # High-frequency details (texture, fabric)
        "OUT_Final_Sharpness": [18]         # Final pixel refinement
    }

    # UI Slider Order
    ORDERED_KEYS = [
        "IN_Layout_Geometry",
        "IN_Perspective_Masses",
        "IN_Subject_Identity",
        "IN_Global_Composition",
        "MID_Core_Concept",
        "OUT_Art_Style_Medium",
        "OUT_Material_Substance",
        "OUT_Lighting_Atmosphere",
        "OUT_Shadows_Depth",
        "OUT_Texture_Details",
        "OUT_Final_Sharpness"
    ]

    @classmethod
    def INPUT_TYPES(s):
        inputs = {
            "required": {
                "model": ("MODEL",),
                "mode": (["Soft Value", "Real Value"],),
                "base_scale": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.01, "tooltip": "Global multiplier applied to all blocks before individual tuning."}),
                "vectors_override": ("STRING", {"default": "", "multiline": False, "placeholder": "Optional: Comma-separated list of 19 floats."}),
            }
        }
        
        # Generate UI sliders dynamically
        for name in s.ORDERED_KEYS:
            inputs["required"][name] = ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.01})
            
        return inputs

    RETURN_TYPES = ("MODEL", "STRING", )
    RETURN_NAMES = ("MODEL", "info", )
    FUNCTION = "tune_model"
    CATEGORY = "Arthemy/SDXL"

    def tune_model(self, model, mode, base_scale, vectors_override, **kwargs):
        
        def get_target_weight(w):
            if mode == "Real Value": return w
            # Soft Value: Quadratic curve for smoother transitions near 1.0
            if w <= 1.0: return max(0.0, -1.02 * (w**2) + 2.02 * w)
            return 1.0 + (w - 1.0) * 0.133

        # Initialize weights
        final_weights = [1.0] * 19
        use_vector = False

        # Option 1: Parse Vector Override
        if vectors_override.strip():
            try:
                v_vals = [float(v.strip()) for v in vectors_override.split(',') if v.strip()]
                if len(v_vals) == 19:
                    final_weights = [get_target_weight(v) for v in v_vals]
                    use_vector = True
                else:
                    print(f"[Arthemy Model Tuner] Warning: Vector override expects 19 values, found {len(v_vals)}. Fallback to sliders.")
            except ValueError:
                print("[Arthemy Model Tuner] Error: Invalid vector string format.")

        # Option 2: Use Grouped Sliders
        if not use_vector:
            for group_name, indices in self.GROUP_MAP.items():
                slider_val = kwargs.get(group_name, 1.0)
                real_val = get_target_weight(slider_val)
                for idx in indices:
                    if 0 <= idx < 19:
                        final_weights[idx] = real_val

        # Map weights to internal block keys
        # Indices: 0-8 (Input), 9 (Middle), 10-18 (Output)
        weights_dict = {}
        for i in range(9): weights_dict[f"IN_{i}"] = final_weights[i]
        weights_dict["MID"] = final_weights[9]
        for i in range(9): weights_dict[f"OUT_{i}"] = final_weights[10+i]

        w_base = get_target_weight(base_scale)
        model_out = model.clone()
        kp = model_out.get_key_patches("diffusion_model.")
        
        active_patches = 0

        for key in kp:
            target_weight = w_base
            
            # Determine block type and index from key
            if "input_blocks" in key:
                match = re.search(r"input_blocks\.(\d+)\.", key)
                if match and int(match.group(1)) <= 8:
                    target_weight = weights_dict.get(f"IN_{int(match.group(1))}", w_base)
            
            elif "middle_block" in key:
                target_weight = weights_dict.get("MID", w_base)
                
            elif "output_blocks" in key:
                match = re.search(r"output_blocks\.(\d+)\.", key)
                if match and int(match.group(1)) <= 8:
                    target_weight = weights_dict.get(f"OUT_{int(match.group(1))}", w_base)

            # Apply weight modification
            strength = target_weight - 1.0
            if strength != 0:
                model_out.add_patches({key: kp[key]}, strength, 1.0)
                active_patches += 1

        info = f"Model Tuned | Mode: {mode} | Patches: {active_patches}"
        return (model_out, info, )

NODE_CLASS_MAPPINGS = {"ArthemyLiveModelTunerSDXL": ArthemyLiveModelTunerSDXL}
NODE_DISPLAY_NAME_MAPPINGS = {"ArthemyLiveModelTunerSDXL": "✨ Arthemy Model Tuner (SDXL)"}