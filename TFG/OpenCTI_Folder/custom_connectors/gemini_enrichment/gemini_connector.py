import os
import time
import json
import google.generativeai as genai
from pycti import OpenCTIConnectorHelper, get_config_variable

class GeminiEnrichmentConnector:
    def __init__(self):
        # 1. Instanciar el helper de opencti
        self.helper = OpenCTIConnectorHelper({})

        # 2. Leer configuración desde Docker (Variables de Entorno)
        # Esto cogerá los valores que definamos luego en el compose
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        self.gemini_model = os.environ.get("GEMINI_MODEL", "gemini-3-pro-preview")
        
        # Configuramos parámetros de la IA (Creatividad vs Precisión)
        try:
            self.gemini_temperature = float(os.environ.get("GEMINI_TEMPERATURE", "0.2"))
            self.gemini_max_tokens = int(os.environ.get("GEMINI_MAX_TOKENS", "2048"))
        except ValueError:
            self.gemini_temperature = 0.2
            self.gemini_max_tokens = 2048

        # Chequeo de seguridad: Si no hay clave, no arrancamos
        if not self.gemini_api_key:
            raise ValueError("¡Error! Falta la variable GEMINI_API_KEY en el entorno.")

        # 3. Configurar el cliente de Gemini
        genai.configure(api_key=self.gemini_api_key)
        self.model = genai.GenerativeModel(
            model_name=self.gemini_model,
            generation_config={
                "temperature": self.gemini_temperature,
                "max_output_tokens": self.gemini_max_tokens,
            }
        )

    def _generate_analysis(self, entity_type, entity_name, description, stix_objects):
        """
        Esta función envía la orden a Google Gemini en ESPAÑOL.
        """
        # Convertimos los objetos STIX a texto para que la IA los lea
        data_context = json.dumps(stix_objects, indent=2, default=str)
        
        # --- EL PROMPT EN ESPAÑOL ---
        prompt = f"""
        ACTÚA COMO UN ANALISTA DE INTELIGENCIA DE CIBERSEGURIDAD EXPERTO.
        
        TAREA: Realiza un análisis técnico y ejecutivo de la siguiente entidad:
        - Tipo: {entity_type}
        - Nombre: "{entity_name}"
        - Contexto previo: {description}
        
        DATOS TÉCNICOS DISPONIBLES (STIX):
        {data_context}

        FORMATO DE SALIDA (MARKDOWN):
        Por favor, genera un informe estructurado en español con las siguientes secciones:
        
        ### 1. Resumen
        Breve descripción del riesgo, nivel de peligrosidad y familia de malware/actor si se conoce.
        
        ### 2. Análisis Técnico
        Detalla capacidades, TTPs (Tácticas, Técnicas y Procedimientos), indicadores relacionados y comportamiento observado en los datos proporcionados.
        
        ### 3. Recomendaciones de Mitigación
        Pasos concretos para defenderse o remediar esta amenaza.
        
        IMPORTANTE:
        - Sé preciso y técnico.
        - Si falta información en los datos, indícalo claramente (no inventes).
        - Usa negritas para resaltar lo importante.
        """
        
        try:
            # Enviamos la petición a Google
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            self.helper.log_error(f"Error conectando con Gemini AI: {e}")
            return f"Error generando análisis: {str(e)}"

    def _process_message(self, data: dict):
        """
        Esta función se activa cuando pulsas el botón en OpenCTI.
        """
        entity_id = data["entity_id"]
        
        # 1. Recuperar toda la información del objeto desde OpenCTI
        entity = self.helper.api.stix_domain_object.read(id=entity_id)
        if not entity:
            self.helper.log_error(f"No se encuentra la entidad {entity_id}")
            return

        self.helper.log_info(f"Iniciando análisis Gemini para: {entity.get('name', 'Desconocido')}")

        # 2. Llamar a la IA
        analysis_text = self._generate_analysis(
            entity_type=entity["entity_type"],
            entity_name=entity.get("name", "Desconocido"),
            description=entity.get("description", "Sin descripción previa"),
            stix_objects=entity # Le pasamos todo lo que sabemos del objeto
        )

        # 3. Guardar el resultado como una NOTA en OpenCTI
        # Creamos una "Nota de Análisis" pegada al objeto
        self.helper.api.note.create(
            abstract=f"Análisis IA (Gemini): {entity.get('name', 'Desconocido')}",
            content=analysis_text,
            created_by_ref=entity.get("createdBy"),
            object_marking_refs=entity.get("objectMarking"),
            object_refs=[entity_id] # Vinculamos la nota al objeto analizado
        )
        
        self.helper.log_info(f"Análisis completado y guardado para {entity.get('name')}")

    def start(self):
        # El conector se queda escuchando eventos de enriquecimiento
        self.helper.listen(self._process_message)

if __name__ == "__main__":
    try:
        connector = GeminiEnrichmentConnector()
        connector.start()
    except Exception as e:
        print(f"Error fatal iniciando Gemini Connector: {e}")
        time.sleep(10)
        exit(1)
