"""
clients/web_ui/gradio_app.py - gradio 6.x, custom HTML before/after slider with ZOOM support
"""
from __future__ import annotations
import base64
import io
import tempfile

import gradio as gr
from loguru import logger
from PIL import Image

from api.worker import worker
from config import users
from config.settings import settings
from core.engine import upscale, MODEL_DISPLAY, GFPGAN_AVAILABLE

_MODEL_GUIDE = """
**💡 Model Rehberi**

| Model | Ne zaman kullan? |
|-------|-----------------|
| 📸 Gerçek Fotoğraf | Portre, manzara, ürün, stüdyo çekimi |
| 🎨 Karakalem / Anime | Çizim, illüstrasyon, manga, sanat eseri |
| 🎬 Video Frame | Karışık içerik, genel amaçlı |

**🔥 Yüz Onarımı (GFPGAN):** Bulanık yüzleri stüdyo kalitesinde onarır.

**🎞 Grain:** Hafif film gürültüsü. 0.10 idealdir.
"""

# İlk açılıştaki boş state (Zoom UI ile birlikte)
_SLIDER_INIT_HTML = """
<div style="position:relative; width:100%; height:580px; border: 1px solid #2a2a2a; border-radius:12px; background:#111; overflow:hidden;">
    <div style="position:absolute; top:12px; right:12px; display:flex; gap:6px; z-index:20;">
        <button disabled style="background:rgba(0,0,0,0.6); color:#555; border:1px solid #333; border-radius:6px; width:32px; height:32px; font-weight:bold;">-</button>
        <button disabled style="background:rgba(0,0,0,0.6); color:#555; border:1px solid #333; border-radius:6px; padding:0 8px; font-weight:bold; font-size:12px;">1.0x</button>
        <button disabled style="background:rgba(0,0,0,0.6); color:#555; border:1px solid #333; border-radius:6px; width:32px; height:32px; font-weight:bold;">+</button>
    </div>
    <div style="width:100%; height:100%; display:flex; align-items:center; justify-content:center; color:#555; font-size:1rem; font-family:'DM Sans',sans-serif;">
        <span>⚡ Görsel yükleyip İşle'ye bas</span>
    </div>
</div>
"""


def _img_to_b64(img: Image.Image, fmt="JPEG") -> str:
    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=92)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _make_slider_html(before_b64: str, after_b64: str) -> str:
    return f"""
<div style="position:relative; width:100%; height:580px; border: 1px solid #2a2a2a; border-radius:12px; background:#111; overflow:hidden;">
    <div style="position:absolute; top:12px; right:12px; display:flex; gap:6px; z-index:20;">
        <button id="yd-zoom-out" style="background:rgba(0,0,0,0.8); color:#fff; border:1px solid #555; border-radius:6px; width:32px; height:32px; cursor:pointer; font-weight:bold; transition: 0.2s;">-</button>
        <button id="yd-zoom-reset" style="background:rgba(0,0,0,0.8); color:#fff; border:1px solid #555; border-radius:6px; padding:0 8px; cursor:pointer; font-weight:bold; font-size:12px; transition: 0.2s;">1.0x</button>
        <button id="yd-zoom-in" style="background:rgba(0,0,0,0.8); color:#fff; border:1px solid #555; border-radius:6px; width:32px; height:32px; cursor:pointer; font-weight:bold; transition: 0.2s;">+</button>
    </div>
    
    <div id="slider-scroll-wrap" style="width:100%; height:100%; overflow:auto; position:relative; scrollbar-width: thin; scrollbar-color: #f5c518 #222;">
        <div id="slider-wrap" style="position:relative; width:100%; height:100%; user-select:none; transition: width 0.1s, height 0.1s;">
            <img src="{before_b64}" style="position:absolute;top:0;left:0;width:100%;height:100%;object-fit:contain;pointer-events:none;"/>
            
            <img id="yd-after-img" src="{after_b64}" style="position:absolute;top:0;left:0;width:100%;height:100%;object-fit:contain;clip-path:inset(0 50% 0 0);pointer-events:none;"/>
            
            <div id="yd-divider" style="position:absolute;top:0;left:50%;width:3px;height:100%;background:#f5c518;transform:translateX(-50%);pointer-events:none;z-index:10;"></div>
            
            <div id="yd-handle" style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:44px;height:44px;background:#f5c518;border-radius:50%;z-index:11;display:flex;align-items:center;justify-content:center;pointer-events:none;box-shadow:0 2px 8px rgba(0,0,0,0.5);font-size:18px;color:#000;font-weight:bold;">⇔</div>
            
            <div style="position:absolute;bottom:12px;right:12px;background:rgba(0,0,0,0.7);color:#fff;padding:4px 10px;border-radius:6px;font-size:12px;font-weight:700;z-index:12;pointer-events:none;">ÖNCE</div>
            <div style="position:absolute;bottom:12px;left:12px;background:#f5c518;color:#000;padding:4px 10px;border-radius:6px;font-size:12px;font-weight:700;z-index:12;pointer-events:none;">SONRA</div>
        </div>
    </div>
</div>
"""


def _process(img, model_label, grain, use_gfpgan, progress=gr.Progress(track_tqdm=True)):
    EMPTY_SLIDER = _SLIDER_INIT_HTML

    if img is None:
        return EMPTY_SLIDER, "❌ Lütfen önce görsel yükleyin.", None

    label_to_key = {v: k for k, v in MODEL_DISPLAY.items()}
    model_key = label_to_key.get(model_label, "photo")

    buf_in = io.BytesIO()
    img.save(buf_in, format="PNG")
    image_bytes = buf_in.getvalue()

    w0, h0 = img.size
    progress(0.10, desc=f"Görsel hazırlandı ({w0}x{h0})")
    n = worker.queue_length()
    progress(0.20, desc=f"Kuyrukta {n} iş var…" if n > 0 else "Kuyruğa ekleniyor…")

    try:
        job = worker.submit(upscale, image_bytes=image_bytes, model_key=model_key,
                            grain=grain, use_gfpgan=use_gfpgan)
    except Exception as e:
        return EMPTY_SLIDER, f"❌ Kuyruk hatası: {e}", None

    progress(0.30, desc="Motor çalışıyor…")
    timed_out = not job.result_event.wait(timeout=settings.WORKER_TIMEOUT + 10)

    if timed_out:
        return EMPTY_SLIDER, "❌ Zaman aşımı!", None
    if job.error:
        return EMPTY_SLIDER, f"❌ Hata: {job.error}", None

    result_img = Image.open(io.BytesIO(job.result))
    w1, h1 = result_img.size
    progress(1.0, desc="Tamamlandı!")

    durum = (f"✅ Tamamlandı!  {w0}x{h0} → {w1}x{h1}  |  "
             f"Model: {MODEL_DISPLAY[model_key]}  |  "
             f"GFPGAN: {'Aktif' if use_gfpgan else 'Kapalı'}  |  "
             f"Grain: {grain:.2f}")
    logger.info(durum)

    # Slider için base64
    before_b64 = _img_to_b64(img)
    after_b64 = _img_to_b64(result_img)
    slider_html = _make_slider_html(before_b64, after_b64)

    # Download için geçici dosya
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp.write(job.result)
    tmp.close()

    return slider_html, durum, tmp.name


def _list_str():
    lst = users.list_users()
    return "\n".join(
        f"{'👑 ' if u == settings.ADMIN_ID else '• '}{u}"
        + ("  (admin)" if u == settings.ADMIN_ID else "")
        for u in lst
    )

def _gui_add(uid_str):
    try:
        return users.add_user(int(uid_str.strip())), _list_str()
    except ValueError:
        return "❌ Geçersiz ID!", _list_str()

def _gui_remove(uid_str):
    try:
        return users.remove_user(int(uid_str.strip())), _list_str()
    except ValueError:
        return "❌ Geçersiz ID!", _list_str()


def build_ui():
    model_choices = list(MODEL_DISPLAY.values())

    with gr.Blocks(title="Yerli Dali AI Studio") as demo:
        gr.HTML("""
        <div style="text-align:center; padding:28px 0 10px;">
            <h1 style="font-size:2.2rem; color:#e8d5a3; margin:0; letter-spacing:-1px; font-weight:800;">
                🎨 Yerli Dali AI Studio
            </h1>
            <p style="color:#888; margin:8px 0 0; font-size:.9rem;">
                Real-ESRGAN · GFPGAN · RTX 4070
            </p>
        </div>
        """)

        with gr.Tabs():
            with gr.Tab("🚀 Upscale"):
                with gr.Row(equal_height=False):

                    # Sol panel
                    with gr.Column(scale=1, min_width=320):
                        input_img = gr.Image(type="pil", label="Görsel Yükle",
                                             height=300, image_mode="RGB")
                        model_radio = gr.Radio(choices=model_choices,
                                               value=model_choices[0], label="Model")
                        gfpgan_check = gr.Checkbox(
                            label="✨ Yüz Onarımı (GFPGAN)",
                            value=GFPGAN_AVAILABLE,
                            interactive=GFPGAN_AVAILABLE,
                            info=("Bulanık yüzleri düzeltir."
                                  if GFPGAN_AVAILABLE else "GFPGAN yüklü değil."),
                        )
                        grain_slider = gr.Slider(
                            minimum=0.00, maximum=0.30,
                            value=settings.DEFAULT_GRAIN, step=0.01,
                            label="🎞 Grain — 0: kapalı · 0.10: hafif · 0.30: belirgin"
                        )
                        gr.Markdown(_MODEL_GUIDE)
                        process_btn = gr.Button("⚡ İşle", variant="primary", size="lg")
                        status_box = gr.Textbox(
                            label="Durum", interactive=False,
                            value="Hazır — görsel yükle ve İşle'ye bas."
                        )
                        download_file = gr.File(label="⬇ İndir", interactive=False)

                    # Sağ panel — custom HTML slider
                    with gr.Column(scale=2):
                        slider_html = gr.HTML(
                            value=_SLIDER_INIT_HTML,
                            label="◀ Önce / Sonra ▶",
                        )

                process_btn.click(
                    fn=_process,
                    inputs=[input_img, model_radio, grain_slider, gfpgan_check],
                    outputs=[slider_html, status_box, download_file],
                ).then(
                    fn=None,
                    inputs=None,
                    outputs=None,
                    js="""
                    () => {
                        setTimeout(() => {
                            const oldWrap = document.getElementById('slider-wrap');
                            if (!oldWrap) return;

                            // Event çakışmalarını sıfırlamak için DOM kopyalama
                            const newWrap = oldWrap.cloneNode(true);
                            oldWrap.parentNode.replaceChild(newWrap, oldWrap);

                            const afterImg = document.getElementById('yd-after-img');
                            const divider = document.getElementById('yd-divider');
                            const handle = document.getElementById('yd-handle');
                            newWrap.style.cursor = 'col-resize';

                            // Slider Pozisyonunu Hesaplama
                            function setPos(x) {
                                const rect = newWrap.getBoundingClientRect();
                                let pct = Math.max(0, Math.min(1, (x - rect.left) / rect.width));
                                let pct_css = (pct * 100) + '%';
                                let rev_pct_css = (100 - pct * 100) + '%';

                                if(afterImg) afterImg.style.clipPath = `inset(0 ${rev_pct_css} 0 0)`;
                                if(divider) divider.style.left = pct_css;
                                if(handle) handle.style.left = pct_css;
                            }

                            // Slider Sürükleme Eventleri
                            let dragging = false;
                            newWrap.addEventListener('mousedown', e => { dragging = true; setPos(e.clientX); e.preventDefault(); });
                            window.addEventListener('mousemove', e => { if (dragging) setPos(e.clientX); });
                            window.addEventListener('mouseup', () => dragging = false);
                            
                            newWrap.addEventListener('touchstart', e => { dragging = true; setPos(e.touches[0].clientX); }, {passive:true});
                            window.addEventListener('touchmove', e => { if (dragging) setPos(e.touches[0].clientX); }, {passive:true});
                            window.addEventListener('touchend', () => dragging = false);

                            // Zoom Kontrolleri (Butonların Eventlerini Sıfırlamak İçin Clone'luyoruz)
                            let btnIn = document.getElementById('yd-zoom-in');
                            let btnOut = document.getElementById('yd-zoom-out');
                            let btnReset = document.getElementById('yd-zoom-reset');
                            
                            if (btnIn) { let clone = btnIn.cloneNode(true); btnIn.parentNode.replaceChild(clone, btnIn); btnIn = clone; }
                            if (btnOut) { let clone = btnOut.cloneNode(true); btnOut.parentNode.replaceChild(clone, btnOut); btnOut = clone; }
                            if (btnReset) { let clone = btnReset.cloneNode(true); btnReset.parentNode.replaceChild(clone, btnReset); btnReset = clone; }

                            let zoomLevel = 100;
                            const scrollWrap = document.getElementById('slider-scroll-wrap');

                            // Merkezi Odaklayarak Zoom Yapan Fonksiyon
                            function updateZoom(newZoom) {
                                if (!scrollWrap) return;
                                
                                // Limitler (Max 5.0x zoom)
                                if (newZoom < 100) newZoom = 100;
                                if (newZoom > 500) newZoom = 500;
                                
                                const oldZoom = zoomLevel;
                                zoomLevel = newZoom;

                                // Büyümeden önce ekranda tam nereye baktığımızı hesaplıyoruz (merkez noktası)
                                const rect = scrollWrap.getBoundingClientRect();
                                const centerX = scrollWrap.scrollLeft + (rect.width / 2);
                                const centerY = scrollWrap.scrollTop + (rect.height / 2);

                                // Eski boyuta göre yeni boyutun oranı
                                const ratio = zoomLevel / oldZoom;

                                // Kutuyu büyüt (580px yükseklik referans alınarak)
                                newWrap.style.width = zoomLevel + '%';
                                newWrap.style.height = (580 * zoomLevel / 100) + 'px';
                                
                                if (btnReset) btnReset.innerText = (zoomLevel / 100).toFixed(1) + 'x';

                                // DOM'un genişlemesi bittikten hemen sonra scroll bar'ı yeni merkeze kaydır
                                requestAnimationFrame(() => {
                                    scrollWrap.scrollLeft = (centerX * ratio) - (rect.width / 2);
                                    scrollWrap.scrollTop = (centerY * ratio) - (rect.height / 2);
                                });
                            }

                            if(btnIn) btnIn.onclick = () => { updateZoom(zoomLevel + 50); };
                            if(btnOut) btnOut.onclick = () => { updateZoom(zoomLevel - 50); };
                            if(btnReset) btnReset.onclick = () => { updateZoom(100); };

                        }, 200);
                    }
                    """
                )

            with gr.Tab("👥 Kullanıcı Yönetimi"):
                with gr.Row():
                    with gr.Column(scale=1):
                        list_box = gr.Textbox(label="İzinli Kullanıcılar",
                                              value=_list_str, interactive=False, lines=12)
                        refresh_btn = gr.Button("🔄 Yenile")
                    with gr.Column(scale=1):
                        uid_input = gr.Textbox(label="Telegram Kullanıcı ID")
                        with gr.Row():
                            add_btn = gr.Button("➕ Ekle", variant="primary")
                            rm_btn = gr.Button("➖ Çıkar", variant="stop")
                        result_box = gr.Textbox(label="İşlem Sonucu", interactive=False)

                refresh_btn.click(fn=_list_str, outputs=list_box)
                add_btn.click(fn=_gui_add, inputs=uid_input, outputs=[result_box, list_box])
                rm_btn.click(fn=_gui_remove, inputs=uid_input, outputs=[result_box, list_box])

    return demo


def launch():
    theme = gr.themes.Base(
        primary_hue=gr.themes.colors.yellow,
        neutral_hue=gr.themes.colors.zinc,
        font=gr.themes.GoogleFont("DM Sans"),
    )
    demo = build_ui()
    demo.launch(
        theme=theme,
        server_name="0.0.0.0",
        server_port=settings.GRADIO_PORT,
        allowed_paths=[str(settings.BASE_DIR)],
        inbrowser=True,
        show_error=True,
        share=False,
    )