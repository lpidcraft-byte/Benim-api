import io
import os
import gc
import torch
from flask import Flask, render_template, request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont
from diffusers import StableDiffusionXLPipeline, AutoencoderKL

app = Flask(__name__)

WATERMARK = "BY VANTORIUM TEAM"
MODEL_ID = "John6666/lustify-v7-sdxl" 
VAE_ID = "madebyollin/sdxl-vae-fp16-fix"

_pipe = None

def get_pipeline():
    global _pipe
    if _pipe is not None:
        return _pipe

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32

    print(f"[+] Kısıtlamasız model yükleniyor: {MODEL_ID}")
    vae = AutoencoderKL.from_pretrained(VAE_ID, torch_dtype=dtype)
    pipe = StableDiffusionXLPipeline.from_pretrained(
        MODEL_ID,
        vae=vae,
        torch_dtype=dtype,
        use_safetensors=True,
    )
    pipe = pipe.to(device)
    pipe.enable_attention_slicing()

    if device == "cuda":
        try:
            pipe.enable_xformers_memory_efficient_attention()
        except Exception:
            pass

    _pipe = pipe
    return _pipe

def add_watermark(img: Image.Image, text: str = WATERMARK) -> Image.Image:
    W, H = img.size
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    font_size = max(18, int(W * 0.028))
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    margin = int(W * 0.03)
    x = W - tw - margin
    y = H - th - margin

    draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, 180))
    draw.text((x, y), text, font=font, fill=(255, 165, 0, 240))
    draw.line([(x, y + th + 4), (x + tw, y + th + 4)], fill=(255, 165, 0, 200), width=2)

    return Image.alpha_composite(img.convert("RGBA"), layer)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json() or {}
    prompt = (data.get("prompt") or "").strip()
    steps = int(data.get("steps", 30))
    guidance = float(data.get("guidance", 7.5))
    seed = data.get("seed")

    if not prompt:
        return jsonify({"error": "prompt boş"}), 400

    try:
        pipe = get_pipeline()
        negative = "" 

        generator = None
        if seed is not None:
            try:
                generator = torch.Generator(device="cuda" if torch.cuda.is_available() else "cpu").manual_seed(int(seed))
            except Exception:
                pass

        with torch.inference_mode():
            image = pipe(
                prompt=prompt,
                negative_prompt=negative,
                num_inference_steps=max(10, min(60, steps)),
                guidance_scale=guidance,
                width=1024,
                height=1024,
                generator=generator,
            ).images[0]

        image = add_watermark(image)

        buf = io.BytesIO()
        image.convert("RGB").save(buf, format="PNG")
        buf.seek(0)

        del image
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()

        return send_file(buf, mimetype="image/png", as_attachment=True, download_name="vantorium.png")

    except torch.cuda.OutOfMemoryError:
        torch.cuda.empty_cache()
        return jsonify({"error": "GPU belleği yetersiz"}), 507
    except Exception as e:
        return jsonify({"error": f"hata: {str(e)}"}), 500

@app.route("/health")
def health():
    return {"status": "ok", "model_loaded": _pipe is not None}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
