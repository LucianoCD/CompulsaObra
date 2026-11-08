"""Servicio de ingesta multimodal con Google GenAI (Gemini 2.5 Flash) y Fallback Determinista."""

import logging
from typing import List, Optional
from google import genai
from google.genai import types

from app.core.config import settings
from app.core.exceptions import MultimodalExtractionUnavailableError
from app.schemas.dimensions import NormalizedItemDraft
from app.schemas.requisition import RequisitionExtractionBatch
from app.services.unit_normalizer import UnitNormalizerService

logger = logging.getLogger(__name__)

# Presets realistas de obra para demostración inmediata en <60 segundos
DEMO_PRESETS: dict[str, str] = {
    "whatsapp_jerga_noa": (
        "50 bolsas de cemento avellaneda\n"
        "40 barras del 8\n"
        "20 hierro del 10\n"
        "4 caño de 3/4\n"
        "5 caño PVC 40 mm"
    ),
    "manuscrito_obra": (
        "20 barra del 8 y 4 caño de 3/4\n"
        "50 bolsas cemento\n"
        "10 caño pvc 110 mm"
    ),
    "computo_tecnico": (
        "100 bolsas cemento portland 50kg\n"
        "60 barra acero aletado diametro 8 mm x 12 m\n"
        "30 barra acero aletado diametro 10 mm x 12 m\n"
        "15 caño pvc sanitario 110 mm x 4 m\n"
        "10 caño pvc sanitario 40 mm x 4 m"
    ),
}


class MultimodalExtractorService:
    """Extrae y normaliza pedidos desde imágenes manuscritas, mensajes de texto o presets."""

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.client: Optional[genai.Client] = None
        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"No se pudo inicializar Google GenAI Client: {e}")

    def extract_from_preset(self, preset_id: str) -> List[NormalizedItemDraft]:
        """Carga y procesa un preset predeterminado en menos de 1 segundo."""
        if preset_id not in DEMO_PRESETS:
            preset_id = "whatsapp_jerga_noa"
        raw_text = DEMO_PRESETS[preset_id]
        return UnitNormalizerService.parse_and_normalize_line(raw_text)

    def extract_from_image_with_gemini(
        self, image_bytes: bytes, mime_type: str = "image/jpeg"
    ) -> List[NormalizedItemDraft]:
        """Invoca Gemini 2.5 Flash con Structured Outputs JSON."""
        if not self.client:
            raise RuntimeError("Gemini Client no inicializado")

        prompt = (
            "Eres un extractor experto de pliegos de materiales de construcción del NOA (Jujuy, Argentina). "
            "Transcribe con máxima precisión cada renglón de la foto manuscrita o documento de obra. "
            "Identifica cantidades numéricas, unidades (bolsas, barras, caños, rollos, unidades), diámetros "
            "(en pulgadas o milímetros), longitudes y materiales."
        )

        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                prompt,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=RequisitionExtractionBatch,
                temperature=0.1,
            ),
        )

        batch: RequisitionExtractionBatch = response.parsed
        # Pasar cada renglón por el normalizador determinista con line_order estrictamente secuencial
        normalized_items: List[NormalizedItemDraft] = []
        item_counter = 1
        for item in batch.items:
            source_line = item.raw_line or f"{item.quantity} {item.requested_term}"
            parsed_list = UnitNormalizerService.parse_and_normalize_line(source_line)
            for p in parsed_list:
                p.line_order = item_counter
                item_counter += 1
                normalized_items.append(p)

        return normalized_items

    def extract_requisition_items(
        self,
        raw_text: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
        preset_id: Optional[str] = None,
        mime_type: str = "image/jpeg",
    ) -> List[NormalizedItemDraft]:
        """Punto de entrada unificado para extracción. No inventa materiales ante fallos de OCR."""
        # 1. Si viene preset explícito (solo vía botón rápido)
        if preset_id:
            return self.extract_from_preset(preset_id)

        # 2. Si viene texto libre (WhatsApp, pegado de lista)
        if raw_text and raw_text.strip():
            return UnitNormalizerService.parse_and_normalize_line(raw_text)

        # 3. Si viene imagen
        if image_bytes:
            if self.client:
                try:
                    return self.extract_from_image_with_gemini(image_bytes, mime_type=mime_type)
                except Exception as e:
                    logger.error(f"Falla en extracción multimodal Gemini: {e}")
                    raise MultimodalExtractionUnavailableError(
                        f"No se pudo extraer la lista de materiales desde la imagen: {str(e)}"
                    )
            
            # Bloqueo honesto CO-02: Nunca inventar datos simulando que se leyó la foto
            raise MultimodalExtractionUnavailableError(
                "El servicio de extracción de imágenes (Gemini) no está configurado (falta GEMINI_API_KEY). "
                "Para probar pedidos de ejemplo utilice la sección 'Presets Rápidos'."
            )

        # Entrada vacía: retornar lista vacía
        return []
