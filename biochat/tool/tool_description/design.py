description = [
    {
        "name": "esm2_generate_sequences",
        "description": (
            "Generate protein sequences using ESM-2 (650M parameters) "
            "protein language model. Given a partial sequence or mask tokens, "
            "ESM-2 predicts the most likely amino acids at each position. "
            "Can be used for sequence design, variant effect prediction, "
            "and protein engineering tasks."
        ),
        "required_parameters": [
            {
                "name": "sequence",
                "type": "str",
                "description": (
                    "Input protein sequence. Use <mask> tokens for positions "
                    "to fill. Example: 'MKFLILFNILV<mask><mask><mask>GALA'"
                ),
                "default": None,
            }
        ],
        "optional_parameters": [
            {
                "name": "num_candidates",
                "type": "int",
                "description": "Number of top-k candidate amino acids to return per position (default: 5)",
                "default": 5,
            },
            {
                "name": "temperature",
                "type": "float",
                "description": "Sampling temperature for sequence generation (default: 1.0)",
                "default": 1.0,
            },
        ],
    }
]
