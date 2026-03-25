from __future__ import annotations
import io
import os
import base64
import logging
from h15hub.adapters.base import DeviceAdapter
from h15hub.models.device import Device, DeviceStatus, ActionResult

logger = logging.getLogger(__name__)

# In-memory SVG cache (icon_name → SVG bytes)
_svg_cache: dict[str, bytes] = {}
TABLER_SVG_URL = "https://cdn.jsdelivr.net/npm/@tabler/icons/icons/{name}.svg"

_ERROR_MAP = {
    "replace media": "Bitte Labelrolle einlegen oder wechseln.",
    "no media":      "Keine Labelrolle eingelegt.",
    "cover open":    "Druckerdeckel ist offen – bitte schließen.",
    "feeding error": "Einzugsfehler – Rolle evtl. falsch eingelegt.",
    "system error":  "Systemfehler am Drucker – Drucker neu starten.",
    "cooling":       "Drucker kühlt ab – bitte kurz warten.",
    "in use":        "Drucker ist gerade belegt.",
    "no label":      "Kein passendes Label eingelegt.",
    "wrong media":   "Falsche Labelgröße eingelegt.",
}

FONTS: dict[str, dict[str, str]] = {
    "dejavu_sans": {
        "name": "DejaVu Sans",
        "regular": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "bold":    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    },
    "dejavu_mono": {
        "name": "DejaVu Mono",
        "regular": "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "bold":    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    },
    "dejavu_serif": {
        "name": "DejaVu Serif",
        "regular": "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "bold":    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    },
}

# QR-Code-Typ → URI-Präfix
QR_TYPE_PREFIXES: dict[str, str] = {
    "text":  "",
    "url":   "",
    "phone": "tel:",
    "sms":   "sms:",
    "email": "mailto:",
}


def _translate_error(msg: str) -> str:
    lower = msg.lower()
    for key, translation in _ERROR_MAP.items():
        if key in lower:
            return translation
    return msg


class LabelprinterAdapter(DeviceAdapter):
    """Adapter für Brother QL Labeldrucker."""

    def __init__(self, config: dict) -> None:
        self.model         = config.get("model", "QL-800")
        self.device_path   = config.get("device", "/dev/usb/lp0")
        self.name          = config.get("name", "Labeldrucker")
        self.default_label = config.get("label", "62")
        self.public        = bool(config.get("public", False))

    async def get_status(self) -> list[Device]:
        available = os.path.exists(self.device_path)
        return [Device(
            id="labelprinter",
            name=self.name,
            type="printer",
            status=DeviceStatus.FREE if available else DeviceStatus.OFFLINE,
            capabilities=["print"] if available else [],
        )]

    async def _fetch_icon_svg(self, name: str) -> bytes | None:
        """Lädt das Tabler-Icon SVG vom CDN (mit In-Memory-Cache)."""
        if not name:
            return None
        if name in _svg_cache:
            return _svg_cache[name]
        try:
            import httpx
            url = TABLER_SVG_URL.format(name=name)
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
            if resp.status_code == 200 and b"<svg" in resp.content:
                _svg_cache[name] = resp.content
                return resp.content
        except Exception as e:
            logger.warning("Icon '%s' konnte nicht geladen werden: %s", name, e)
        return None

    def _svg_to_pil(self, svg_bytes: bytes, size: int) -> "Image.Image | None":
        """Wandelt SVG-Bytes in ein PIL-Bild der Größe size×size um."""
        try:
            import cairosvg
            from PIL import Image
            png = cairosvg.svg2png(bytestring=svg_bytes, output_width=size, output_height=size)
            img = Image.open(io.BytesIO(png)).convert("RGBA")
            # Weißer Hintergrund
            bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            return bg.convert("RGB")
        except Exception as e:
            logger.warning("SVG→PIL fehlgeschlagen: %s", e)
            return None

    def _parse_params(self, params: dict) -> dict:
        text        = (params.get("text") or "").strip()
        qr_text     = (params.get("qr_text") or "").strip()
        qr_type     = params.get("qr_type", "text")
        label_id    = params.get("label", self.default_label)
        font_size   = max(10, min(int(params.get("font_size", 72)), 400))
        font_family = params.get("font_family", "dejavu_sans")
        if font_family not in FONTS:
            font_family = "dejavu_sans"
        align       = params.get("align", "left")
        bold        = bool(params.get("bold", True))
        rotate      = int(params.get("rotate", 0))
        text_rotate = int(params.get("text_rotate", 0))
        qr_size_pct  = max(20, min(int(params.get("qr_size", 80)), 100))
        qr_pos       = params.get("qr_pos", "left")
        icon         = (params.get("icon") or "").strip().lower().replace(" ", "-")
        icon_size_pct = max(20, min(int(params.get("icon_size", 80)), 100))
        icon_pos     = params.get("icon_pos", "right")
        icon_img     = params.get("_icon_img")  # pre-rendered PIL image from async fetch
        if rotate not in (0, 90, 180, 270):
            rotate = 0
        if text_rotate not in (0, 90, 180, 270):
            text_rotate = 0

        # QR-URI aufbauen
        prefix = QR_TYPE_PREFIXES.get(qr_type, "")
        if qr_text and prefix and not qr_text.startswith(prefix):
            qr_text = prefix + qr_text

        return dict(
            text=text, qr_text=qr_text, label_id=label_id,
            font_size=font_size, font_family=font_family,
            align=align, bold=bold,
            rotate=rotate, text_rotate=text_rotate,
            qr_size_pct=qr_size_pct, qr_pos=qr_pos,
            icon=icon, icon_size_pct=icon_size_pct, icon_pos=icon_pos,
            icon_img=icon_img,
        )

    def _build_label_image(self, p: dict):
        """Rendert das Label-Bild. Gibt (PIL.Image, label_id, rotate) zurück."""
        from brother_ql.labels import get_label
        from PIL import Image, ImageDraw, ImageFont

        label_def = get_label(p["label_id"])
        if label_def is None:
            raise ValueError(f"Unbekannte Labelgröße: '{p['label_id']}'")

        print_w     = label_def.dots_printable[0]
        print_h_fix = label_def.dots_printable[1]  # 0 = Endlosband
        margin      = 20
        font_size   = p["font_size"]
        bold        = p["bold"]
        align       = p["align"]
        text        = p["text"]
        qr_text     = p["qr_text"]
        rotate      = p["rotate"]
        text_rotate = p["text_rotate"]
        qr_size_pct  = p["qr_size_pct"]
        qr_pos       = p["qr_pos"]
        icon_img_raw = p.get("icon_img")
        icon_size_pct = p.get("icon_size_pct", 80)
        icon_pos     = p.get("icon_pos", "right")

        font_info = FONTS.get(p["font_family"], FONTS["dejavu_sans"])
        font_file = font_info["bold"] if bold else font_info["regular"]
        try:
            font = ImageFont.truetype(font_file, size=font_size)
        except OSError:
            font = ImageFont.load_default()

        lines = text.splitlines() if text else []

        # Zeilenhöhe messen
        probe  = Image.new("RGB", (print_w, max(font_size * 2 + 10, 10)))
        line_h = ImageDraw.Draw(probe).textbbox((0, 0), "Ag", font=font)[3] + 4 if lines else 0
        total_text_h = line_h * len(lines)

        # Bildhöhe bestimmen
        if print_h_fix > 0:
            img_h = print_h_fix
        else:
            img_h = max(total_text_h + 2 * margin, font_size + 2 * margin)

        # Icon vorbereiten
        icon_img = None
        if icon_img_raw is not None:
            icon_sz = max(20, int((img_h - 2 * margin) * icon_size_pct / 100))
            icon_img = icon_img_raw.resize((icon_sz, icon_sz), Image.LANCZOS)

        # QR-Code generieren
        qr_img = None
        if qr_text:
            import qrcode as _qrcode
            qr = _qrcode.QRCode(
                version=None,
                error_correction=_qrcode.constants.ERROR_CORRECT_M,
                box_size=4,
                border=1,
            )
            qr.add_data(qr_text)
            qr.make(fit=True)
            raw_qr = qr.make_image(fill_color="black", back_color="white").convert("RGB")
            qr_size = max(20, int((img_h - 2 * margin) * qr_size_pct / 100))
            qr_img  = raw_qr.resize((qr_size, qr_size), Image.LANCZOS)

        # Canvas-Größe (Stanzlabels mit 90°/270° brauchen gespiegelte Maße)
        if print_h_fix > 0 and rotate in (90, 270):
            create_w, create_h = print_h_fix, print_w
        else:
            create_w, create_h = print_w, img_h

        img  = Image.new("RGB", (create_w, create_h), color="white")
        draw = ImageDraw.Draw(img)

        # Hilfsfunktion: belegte Breite links/rechts
        left_w  = 0
        right_w = 0

        def paste_side(element, pos):
            nonlocal left_w, right_w
            if pos == "right":
                x = create_w - margin - element.width
                right_w = element.width + margin
            else:
                x = margin
                left_w = element.width + margin
            y = (create_h - element.height) // 2
            img.paste(element, (x, y))

        if qr_img:
            paste_side(qr_img, qr_pos)
        if icon_img:
            # Icon auf der entgegengesetzten Seite wie QR, oder an icon_pos
            actual_icon_pos = icon_pos
            if qr_img and icon_pos == qr_pos:
                actual_icon_pos = "right" if qr_pos == "left" else "left"
            paste_side(icon_img, actual_icon_pos)

        text_x_start = margin + left_w
        text_area_w  = create_w - left_w - right_w - margin

        # Text zeichnen
        if lines:
            if text_rotate != 0:
                max_tw = max(
                    (draw.textbbox((0, 0), l, font=font)[2] for l in lines),
                    default=0,
                )
                tmp = Image.new("RGB", (max_tw + 2 * margin, total_text_h + 2 * margin), "white")
                tmp_draw = ImageDraw.Draw(tmp)
                ty = margin
                for line in lines:
                    tmp_draw.text((margin, ty), line, fill="black", font=font)
                    ty += line_h
                tmp = tmp.rotate(text_rotate, expand=True)
                px = text_x_start + max(0, (text_area_w - tmp.width) // 2)
                py = max(0, (create_h - tmp.height) // 2)
                img.paste(tmp, (px, py))
            else:
                y = (create_h - total_text_h) // 2
                for line in lines:
                    bbox   = draw.textbbox((0, 0), line, font=font)
                    text_w = bbox[2] - bbox[0]
                    if align == "center":
                        x = text_x_start + (text_area_w - text_w) // 2
                    elif align == "right":
                        x = text_x_start + text_area_w - text_w
                    else:
                        x = text_x_start
                    draw.text((x, y), line, fill="black", font=font)
                    y += line_h

        return img, p["label_id"], rotate

    async def execute_action(self, device_id: str, action: str, params: dict) -> ActionResult:
        if action == "preview":
            return await self._action_preview(params)
        if action == "print":
            return await self._action_print(params)
        return ActionResult(success=False, message=f"Unbekannte Aktion: {action}")

    async def _resolve_icon(self, params: dict) -> dict:
        """Holt Icon-SVG und rendert es zu PIL, fügt _icon_img in params ein."""
        icon_name = (params.get("icon") or "").strip()
        if icon_name:
            svg = await self._fetch_icon_svg(icon_name)
            if svg:
                # Temporäre Größe, wird in _build_label_image nochmal skaliert
                params = dict(params, _icon_img=self._svg_to_pil(svg, 128))
        return params

    async def _action_preview(self, params: dict) -> ActionResult:
        try:
            params = await self._resolve_icon(params)
            p   = self._parse_params(params)
            img, _, _ = self._build_label_image(p)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            png_b64 = base64.b64encode(buf.getvalue()).decode()
            return ActionResult(success=True, message="", data={"png_b64": png_b64})
        except Exception as e:
            return ActionResult(success=False, message=_translate_error(str(e)))

    async def _action_print(self, params: dict) -> ActionResult:
        text    = (params.get("text") or "").strip()
        qr_text = (params.get("qr_text") or "").strip()
        if not text and not qr_text:
            return ActionResult(success=False, message="Kein Text oder QR-Inhalt angegeben.")

        try:
            import asyncio
            from brother_ql.conversion import convert
            from brother_ql.raster import BrotherQLRaster

            params = await self._resolve_icon(params)
            p   = self._parse_params(params)
            img, label_id, rotate = self._build_label_image(p)

            qlr = BrotherQLRaster(self.model)
            qlr.exception_on_warning = True
            instructions = convert(
                qlr, [img], label_id,
                cut=True, rotate=rotate,
            )

            def _write(path: str, data: bytes) -> None:
                with open(path, "wb") as f:
                    f.write(data)

            await asyncio.to_thread(_write, self.device_path, instructions)
            return ActionResult(success=True, message="Label erfolgreich gedruckt.")
        except Exception as e:
            return ActionResult(success=False, message=_translate_error(str(e)))
