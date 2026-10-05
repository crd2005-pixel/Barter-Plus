import os
from typing import Optional
from google import genai
from pydantic import BaseModel, Field

# Initialize client using environment variable GEMINI_API_KEY
client = genai.Client()

class GeneratedPost(BaseModel):
    hook: str = Field(description="Gancho inicial magnético según el formato.")
    body: str = Field(description="Desarrollo del copy (incluyendo estructura por líneas o saltos de párrafo).")
    cta: str = Field(description="Llamada a la acción clara alineada al objetivo.")
    hashtags: str = Field(description="5 a 10 hashtags relevantes separados por espacio.")
    visual_idea: str = Field(description="Instrucción detallada de qué imagen, carrusel o video debe crearse para acompañar este texto.")

def generate_post_content(brand, pillar_name: Optional[str], post_format: str, extra_topic: Optional[str] = None) -> GeneratedPost:
    """
    Generates a post based on brand guidelines using the Gemini model.
    Forces response into the GeneratedPost JSON structure.
    """

    prompt = f"""
    Eres un Community Manager Experto. Tu objetivo es escribir un post altamente atractivo
    para la siguiente marca:

    - Nombre: {brand.name}
    - Nicho: {brand.niche}
    - Público Objetivo: {brand.target_audience}
    - Tono y Estilo (Voz): {brand.brand_voice}

    Requerimientos del Post:
    - Formato: {post_format}
    - Pilar de contenido: {pillar_name if pillar_name else "General"}
    """

    if extra_topic:
        prompt += f"\n    - Tema específico a incluir: {extra_topic}\n"

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'response_schema': GeneratedPost,
            },
        )
        return GeneratedPost.model_validate_json(response.text)
    except Exception as e:
        # Handling for connection errors, invalid keys, or schema parse failures
        raise RuntimeError(f"Error generando contenido con IA: {str(e)}")
