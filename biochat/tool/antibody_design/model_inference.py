import torch
import torch.nn as nn
import torch.nn.functional as F
import math
import os
import numpy as np
from collections import Counter

# --- 词汇表与常量 ---
VOCAB = "ACDEFGHIKLMNPQRSTVWYX-"
AA_TO_ID = {aa: i for i, aa in enumerate(VOCAB)}
ID_TO_AA = {i: aa for aa, i in AA_TO_ID.items()}
VOCAB_SIZE = len(VOCAB)
CANONICAL_AAS = set("ACDEFGHIKLMNPQRSTVWY")
PAD_ID = AA_TO_ID["-"]
X_ID = AA_TO_ID["X"]
AROMATIC_AAS = set("YFW")


class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, dropout: float = 0.1, max_len: int = 50):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)
        position = torch.arange(max_len).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2) * (-math.log(10000.0) / d_model))
        pe = torch.zeros(max_len, 1, d_model)
        pe[:, 0, 0::2] = torch.sin(position * div_term)
        pe[:, 0, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe', pe)

    def forward(self, x):
        x = x.transpose(0, 1)
        x = x + self.pe[:x.size(0)]
        x = self.dropout(x)
        return x.transpose(0, 1)


class TransformerVAE(nn.Module):
    def __init__(self, alphabet_size, d_model, nhead, num_encoder_layers, num_decoder_layers, latent_dim, max_len):
        super().__init__()
        self.d_model = d_model
        self.max_len = max_len
        self.embedding = nn.Embedding(alphabet_size, d_model, padding_idx=AA_TO_ID['-'])
        self.pos_encoder = PositionalEncoding(d_model, max_len=max_len)
        encoder_layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=nhead, batch_first=True, activation='gelu')
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_encoder_layers)
        self.fc_mu = nn.Linear(d_model * max_len, latent_dim)
        self.fc_logvar = nn.Linear(d_model * max_len, latent_dim)
        self.latent_to_hidden = nn.Linear(latent_dim, d_model * max_len)
        decoder_layer = nn.TransformerDecoderLayer(d_model=d_model, nhead=nhead, batch_first=True, activation='gelu')
        self.transformer_decoder = nn.TransformerDecoder(decoder_layer, num_layers=num_decoder_layers)
        self.output_proj = nn.Linear(d_model, alphabet_size)

    def encode(self, src, src_mask):
        src_emb = self.embedding(src) * math.sqrt(self.d_model)
        src_emb = self.pos_encoder(src_emb)
        padding_mask = (src_mask == 0)
        encoder_output = self.transformer_encoder(src_emb, src_key_padding_mask=padding_mask)
        flat_output = encoder_output.view(encoder_output.size(0), -1)
        mu = self.fc_mu(flat_output)
        logvar = self.fc_logvar(flat_output)
        return mu, logvar

    def decode(self, z):
        hidden = self.latent_to_hidden(z).view(-1, self.max_len, self.d_model)
        hidden = self.pos_encoder(hidden)
        decoder_output = self.transformer_decoder(hidden, hidden)
        logits = self.output_proj(decoder_output)
        return logits


class ConditionalDenoisingNet(nn.Module):
    def __init__(self, latent_dim, num_layers=4, num_heads=4):
        super().__init__()
        self.time_embedding = nn.Embedding(1000, latent_dim)
        self.cross_attention = nn.MultiheadAttention(latent_dim, num_heads, batch_first=True)
        self.norm_cross = nn.LayerNorm(latent_dim)
        self.layers = nn.ModuleList([
            nn.TransformerEncoderLayer(d_model=latent_dim, nhead=num_heads, batch_first=True, activation='gelu') for _
            in range(num_layers)
        ])
        self.output_proj = nn.Linear(latent_dim, latent_dim)

    def forward(self, x, t, condition_embedding):
        time_emb = self.time_embedding(t)
        x = x + time_emb
        x_seq = x.unsqueeze(1)
        cond_seq = condition_embedding.unsqueeze(1)
        x_attn, _ = self.cross_attention(query=x_seq, key=cond_seq, value=cond_seq)
        x = self.norm_cross(x + x_attn.squeeze(1))
        x_seq = x.unsqueeze(1)
        for layer in self.layers:
            x_seq = layer(x_seq)
        x = x_seq.squeeze(1)
        return self.output_proj(x)


class ConditionalDiffusion(nn.Module):
    def __init__(self, latent_dim, timesteps=1000, num_layers=4):
        super().__init__()
        self.timesteps = timesteps
        self.denoising_model = ConditionalDenoisingNet(latent_dim, num_layers=num_layers)
        betas = torch.linspace(0.0001, 0.02, timesteps)
        self.register_buffer('betas', betas)
        alphas = 1. - betas
        self.register_buffer('alphas', alphas)
        alphas_cumprod = torch.cumprod(alphas, axis=0)
        self.register_buffer('alphas_cumprod', alphas_cumprod)
        self.register_buffer('sqrt_alphas_cumprod', torch.sqrt(self.alphas_cumprod))
        self.register_buffer('sqrt_one_minus_alphas_cumprod', torch.sqrt(1. - self.alphas_cumprod))

    def forward(self, x0, t, condition_embedding):
        noise = torch.randn_like(x0)
        xt = self.sqrt_alphas_cumprod[t].view(-1, 1) * x0 + self.sqrt_one_minus_alphas_cumprod[t].view(-1, 1) * noise
        predicted_noise = self.denoising_model(xt, t, condition_embedding)
        return F.mse_loss(predicted_noise, noise)


class DiffCDRH3(nn.Module):
    def __init__(self, cdrh3_vae: TransformerVAE, epitope_vae: TransformerVAE, latent_dim, timesteps=1000,
                 num_layers_diff=4):
        super().__init__()
        self.cdrh3_vae = cdrh3_vae
        self.epitope_vae = epitope_vae
        self.diffusion = ConditionalDiffusion(latent_dim, timesteps, num_layers_diff)
        for param in self.cdrh3_vae.latent_to_hidden.parameters(): param.requires_grad = False
        for param in self.cdrh3_vae.transformer_decoder.parameters(): param.requires_grad = False
        for param in self.cdrh3_vae.output_proj.parameters(): param.requires_grad = False
        for param in self.epitope_vae.latent_to_hidden.parameters(): param.requires_grad = False
        for param in self.epitope_vae.transformer_decoder.parameters(): param.requires_grad = False
        for param in self.epitope_vae.output_proj.parameters(): param.requires_grad = False

    def forward(self, cdrh3_seq_idx, epitope_seq_idx, cdrh3_mask, epitope_mask):
        mu_c, _ = self.cdrh3_vae.encode(cdrh3_seq_idx, cdrh3_mask)
        mu_e, _ = self.epitope_vae.encode(epitope_seq_idx, epitope_mask)
        t = torch.randint(0, self.diffusion.timesteps, (cdrh3_seq_idx.shape[0],), device=cdrh3_seq_idx.device).long()
        diffusion_loss = self.diffusion(mu_c, t, mu_e)
        return diffusion_loss


def load_pretrained_model(weights_path: str, device: str):
    """
    初始化模型架构并加载权重
    """
    # 超参数必须与训练时一致
    D_MODEL = 128
    NHEAD = 4
    LATENT_DIM = 64
    CDRH3_ENC_LAYERS = 4
    CDRH3_DEC_LAYERS = 1
    CDRH3_MAX_LEN = 30
    EPI_ENC_LAYERS = 4
    EPI_DEC_LAYERS = 1
    EPITOPE_MAX_LEN = 24
    DIFF_LAYERS = 4

    cdrh3_vae = TransformerVAE(VOCAB_SIZE, D_MODEL, NHEAD, CDRH3_ENC_LAYERS, CDRH3_DEC_LAYERS, LATENT_DIM,
                               CDRH3_MAX_LEN)
    epitope_vae = TransformerVAE(VOCAB_SIZE, D_MODEL, NHEAD, EPI_ENC_LAYERS, EPI_DEC_LAYERS, LATENT_DIM,
                                 EPITOPE_MAX_LEN)
    model = DiffCDRH3(cdrh3_vae, epitope_vae, LATENT_DIM, num_layers_diff=DIFF_LAYERS)

    try:
        # 添加 map_location 以防你在没有 GPU 的机器上测试
        state_dict = torch.load(weights_path, map_location=device, weights_only=True)
        model.load_state_dict(state_dict, strict=False)
        model.to(device)
        model.eval()
        print(f"模型成功加载: {weights_path}")
        return model
    except Exception as e:
        print(f"加载模型失败: {e}")
        return None


# --- 生成后序列验证 (module-level, usable by tests) ---
def _validate_generated_sequence(seq: str):
    """Post-generation hard validation. Returns (is_valid, rejection_reason).

    Module-level function so tests can import and use it directly.
    """
    if not seq or len(seq) < 6:
        return False, "too_short"
    if len(seq) > 32:
        return False, "too_long"

    counts = Counter(seq)
    length = len(seq)

    # Check single AA fraction
    max_aa, max_count = counts.most_common(1)[0]
    if max_count / length > 0.35:
        return False, f"excessive_single_aa_{max_aa}_{max_count / length:.2f}"

    # Check poly-run
    max_run = 1
    cur_run = 1
    for i in range(1, length):
        if seq[i] == seq[i - 1]:
            cur_run += 1
            max_run = max(max_run, cur_run)
        else:
            cur_run = 1
    if max_run > 3:
        return False, f"poly_run_{max_run}"

    # Check aromatic fraction
    aromatic_count = sum(counts.get(aa, 0) for aa in AROMATIC_AAS)
    if aromatic_count / length > 0.45:
        return False, f"excessive_aromatic_{aromatic_count / length:.2f}"

    # Check Gly/Pro fraction (flexibility)
    gp_count = counts.get("G", 0) + counts.get("P", 0)
    if gp_count / length > 0.5:
        return False, f"excessive_gp_{gp_count / length:.2f}"

    # Check Cys
    if "C" in seq:
        return False, "contains_cysteine"

    return True, ""


# --- 生成函数 (稍微修改以去除 tqdm，防止在接口端产生过多日志) ---
def generate_cdrh3(model, epitope_sequence, device, num_samples=5, cdrh3_max_len=30, epitope_max_len=24, latent_dim=64,
                   length_prior=None):
    """接收表位，生成指定数量的 CDRH3。

    Args:
        length_prior: Optional dict from target_analyzer with keys:
            recommended_min, recommended_max, hard_max, distribution_mode
            If provided, controls variable-length sampling.
    """
    length_prior = length_prior or {}
    rec_min = int(length_prior.get("recommended_min", 9))
    rec_max = int(length_prior.get("recommended_max", 20))
    hard_max = min(cdrh3_max_len, int(length_prior.get("hard_max", 30)))

    def _process_seq(seq, max_len):
        seq_ids = [AA_TO_ID.get(aa, AA_TO_ID['X']) for aa in str(seq)]
        seq_len = min(len(seq_ids), max_len)
        seq_ids = seq_ids[:max_len]
        mask = [1] * seq_len + [0] * (max_len - seq_len)
        if len(seq_ids) < max_len:
            seq_ids.extend([AA_TO_ID['-']] * (max_len - len(seq_ids)))
        return torch.tensor(seq_ids, dtype=torch.long), torch.tensor(mask, dtype=torch.long)

    def _sanitize_generated_seq(seq: str) -> str:
        # ABodyBuilder2 不接受未知氨基酸，这里把 X 保守替换为 G。
        cleaned = []
        for aa in seq:
            if aa in CANONICAL_AAS:
                cleaned.append(aa)
            elif aa == 'X':
                cleaned.append('G')
        return "".join(cleaned)

    def _apply_top_p(logits_row: torch.Tensor, top_p: float) -> torch.Tensor:
        if top_p >= 1.0:
            return logits_row
        probs = torch.softmax(logits_row, dim=-1)
        sorted_probs, sorted_indices = torch.sort(probs, descending=True)
        cumulative = torch.cumsum(sorted_probs, dim=-1)
        to_remove = cumulative > top_p
        if to_remove.numel() > 0:
            to_remove[0] = False
        remove_mask = torch.zeros_like(to_remove, dtype=torch.bool)
        remove_mask.scatter_(0, sorted_indices, to_remove)
        logits_row = logits_row.masked_fill(remove_mask, float("-inf"))
        return logits_row

    def _sample_token(logits_row: torch.Tensor) -> int:
        probs = torch.softmax(logits_row, dim=-1)
        if torch.isnan(probs).any() or torch.isinf(probs).all():
            return int(torch.argmax(logits_row).item())
        return int(torch.multinomial(probs, num_samples=1).item())

    # ---- length-aware parameters (from target_analyzer priors, env-overridable) ----
    gen_min_len = max(6, int(os.getenv("CDRH3_GEN_MIN_LEN", str(rec_min))))
    gen_soft_max = min(hard_max, int(os.getenv("CDRH3_GEN_SOFT_MAX_LEN", str(rec_max))))
    gen_hard_max = min(cdrh3_max_len, int(os.getenv("CDRH3_GEN_HARD_MAX", str(hard_max))))

    def _sample_sequence_from_logits(logits_seq: torch.Tensor) -> str:
        stop_boost = float(os.getenv("CDRH3_GEN_STOP_BOOST", "4.0"))
        temperature = float(os.getenv("CDRH3_GEN_TEMPERATURE", "1.15"))
        top_k = int(os.getenv("CDRH3_GEN_TOPK", "8"))
        top_p = float(os.getenv("CDRH3_GEN_TOPP", "0.9"))
        repetition_penalty = float(os.getenv("CDRH3_GEN_REPEAT_PENALTY", "3.2"))
        comp_penalty = float(os.getenv("CDRH3_GEN_COMPOSITION_PENALTY", "2.4"))
        hard_max_single_aa = float(os.getenv("CDRH3_HARD_MAX_SINGLE_AA", "0.25"))
        hard_max_aromatic = float(os.getenv("CDRH3_HARD_MAX_AROMATIC", "0.40"))
        hard_poly_run = int(os.getenv("CDRH3_HARD_POLY_RUN", "3"))

        generated = []
        effective_max = min(logits_seq.size(0), gen_hard_max)
        for pos in range(effective_max):
            token_logits = logits_seq[pos].clone() / max(0.4, temperature)

            # Strongly suppress X; use PAD (-) as length-control stop token
            token_logits[X_ID] -= 8.0

            if pos < gen_min_len:
                token_logits[PAD_ID] = float("-inf")
            elif pos >= gen_soft_max:
                # Past recommended max: strong stop pressure
                overshoot = pos - gen_soft_max + 1
                token_logits[PAD_ID] += stop_boost * 2.0 + 2.5 * overshoot
            else:
                # Between min and recommended max: mild stop pressure
                token_logits[PAD_ID] += max(0.0, stop_boost + 0.35 * (pos - gen_min_len))

            if generated:
                counts = Counter(generated)
                last_aa = generated[-1]
                run_len = 1
                for j in range(len(generated) - 2, -1, -1):
                    if generated[j] == last_aa:
                        run_len += 1
                    else:
                        break

                last_id = AA_TO_ID[last_aa]
                # Hard block: poly-run >= hard_poly_run
                if run_len >= hard_poly_run:
                    token_logits[last_id] = float("-inf")
                elif run_len >= 2:
                    token_logits[last_id] -= repetition_penalty * (run_len - 1)
                if run_len >= 3:
                    token_logits[last_id] -= repetition_penalty * 2.0

                next_len = len(generated) + 1
                for aa, count in counts.items():
                    aa_id = AA_TO_ID[aa]
                    future_fraction = (count + 1) / next_len
                    # Hard block: single AA > hard_max_single_aa
                    if future_fraction > hard_max_single_aa + 0.05:
                        token_logits[aa_id] = float("-inf")
                    elif future_fraction > hard_max_single_aa:
                        token_logits[aa_id] -= comp_penalty * 3.0
                    elif future_fraction > 0.26:
                        token_logits[aa_id] -= comp_penalty

                aromatic_fraction = sum(counts[aa] for aa in AROMATIC_AAS) / len(generated)
                if aromatic_fraction > hard_max_aromatic:
                    for aa in AROMATIC_AAS:
                        token_logits[AA_TO_ID[aa]] = float("-inf")
                elif aromatic_fraction > 0.35:
                    for aa in AROMATIC_AAS:
                        token_logits[AA_TO_ID[aa]] -= comp_penalty * 1.6

            if top_k > 0 and top_k < token_logits.numel():
                kth = torch.topk(token_logits, top_k).values[-1]
                token_logits = torch.where(token_logits < kth, torch.full_like(token_logits, float("-inf")), token_logits)
            token_logits = _apply_top_p(token_logits, top_p)

            token_id = _sample_token(token_logits)
            if token_id == PAD_ID:
                break
            aa = ID_TO_AA.get(token_id, "-")
            if aa in CANONICAL_AAS or aa == "X":
                generated.append(aa)

        seq = _sanitize_generated_seq("".join(generated))
        if not seq:
            fallback_ids = torch.argmax(logits_seq, dim=-1)
            fallback = "".join(ID_TO_AA.get(idx.item(), "-") for idx in fallback_ids)
            seq = _sanitize_generated_seq(fallback.replace("-", ""))
        return seq or "GGSGG"

    epitope_idx, epitope_mask = _process_seq(epitope_sequence, epitope_max_len)
    epitope_idx = epitope_idx.unsqueeze(0).to(device)
    epitope_mask = epitope_mask.unsqueeze(0).to(device)

    with torch.no_grad():
        epitope_latent, _ = model.epitope_vae.encode(epitope_idx, epitope_mask)
        condition = epitope_latent.repeat(num_samples, 1)
        xt = torch.randn((num_samples, latent_dim), device=device)

        inference_steps = int(os.getenv("DIFFUSION_INFERENCE_STEPS", "250"))
        inference_steps = max(20, min(model.diffusion.timesteps, inference_steps))
        if inference_steps >= model.diffusion.timesteps:
            timesteps = list(range(model.diffusion.timesteps - 1, -1, -1))
        else:
            timesteps = sorted(set(np.linspace(0, model.diffusion.timesteps - 1, inference_steps, dtype=int).tolist()), reverse=True)

        # 去掉了 tqdm 进度条，因为在网页端这没用
        for t in timesteps:
            time_tensor = torch.full((num_samples,), t, device=device, dtype=torch.long)
            predicted_noise = model.diffusion.denoising_model(xt, time_tensor, condition)

            alpha_t = model.diffusion.alphas[t]
            alpha_t_cumprod = model.diffusion.alphas_cumprod[t]
            beta_t = model.diffusion.betas[t]
            sigma = torch.sqrt(beta_t)

            mean = (1 / torch.sqrt(alpha_t)) * (
                    xt - ((1 - alpha_t) / torch.sqrt(1 - alpha_t_cumprod)) * predicted_noise)
            if t > 0:
                noise = torch.randn_like(xt)
                xt = mean + sigma * noise
            else:
                xt = mean

        generated_latent = xt
        logits = model.cdrh3_vae.decode(generated_latent)

        generated_sequences = []
        rejected_count = 0

        for i in range(num_samples):
            for retry in range(3):  # up to 3 attempts per slot
                seq = _sample_sequence_from_logits(logits[i])
                is_valid, reason = _validate_generated_sequence(seq)
                if is_valid:
                    generated_sequences.append(seq)
                    break
                rejected_count += 1
                if retry == 2:
                    # Last attempt: keep it but flag
                    generated_sequences.append(seq)
                    print(f"[CDRH3 GEN] Candidate {i}: all retries failed, kept with: {reason}")

        if rejected_count > 0:
            print(f"[CDRH3 GEN] Rejected {rejected_count} sequences during validation")

    return generated_sequences
