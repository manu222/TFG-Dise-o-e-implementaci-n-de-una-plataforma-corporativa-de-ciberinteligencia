import os
import time
import json
import requests
import ipaddress
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any

from pycti import OpenCTIConnectorHelper
from stix2 import (
    Bundle, Malware, IPv4Address, DomainName, URL, 
    Relationship, Identity, Indicator
)

# Constantes de seguridad
MAX_FILE_SIZE_MB = 10
TIMEOUT_SECONDS = 30

class MultiFeedConnector:
    """
    Conector de Ingesta de Amenazas Multi-Fuente (TFG).
    """

    def __init__(self):
        self.helper = OpenCTIConnectorHelper({})
        self.feeds_config_file = "feeds.json"
        
        self.author = Identity(
            name="TFG Threat Intelligence",
            identity_class="organization",
            description="Ingesta Automática - TFG Ciberseguridad",
            allow_custom=True
        )

    def get_feeds_config(self) -> List[Dict[str, Any]]:
        try:
            if not os.path.exists(self.feeds_config_file):
                self.helper.log_error(f"Fichero de configuración no encontrado: {self.feeds_config_file}")
                return []
            
            with open(self.feeds_config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.helper.log_error(f"Error leyendo configuración: {e}")
            return []

    # --- VALIDADORES ---
    
    def _is_ip_structure(self, text: str) -> bool:
        """Devuelve True si el texto tiene estructura de IP (aunque sea privada/local)."""
        try:
            ipaddress.ip_address(text)
            return True
        except ValueError:
            return False

    def _is_public_ip(self, ip_str: str) -> bool:
        """Devuelve True solo si es una IP PÚBLICA e ingestable."""
        try:
            ip_obj = ipaddress.ip_address(ip_str)
            return ip_obj.is_global and not ip_obj.is_multicast
        except ValueError:
            return False

    def _clean_domain(self, domain: str) -> Optional[str]:
        """Limpia un dominio sucio para dejar solo 'evil.com'."""
        if not domain: return None
        
        domain = str(domain).lower().strip()
        
        if "://" in domain: domain = domain.split("://")[1]
        if "/" in domain: domain = domain.split("/")[0]
        if ":" in domain: domain = domain.split(":")[0]
            
        # Validación final: debe tener al menos un punto y no ser demasiado corto
        if "." not in domain or len(domain) < 3:
            return None
        return domain

    def download_data(self, url: str) -> Optional[str]:
        try:
            with requests.get(url, stream=True, timeout=TIMEOUT_SECONDS) as response:
                response.raise_for_status()
                content = response.text
                return content
        except Exception as e:
            self.helper.log_error(f"Error descarga {url}: {e}")
            return None

    # --- PARSERS ---

    def process_drb_json(self, content: str, labels: List[str]) -> List[Any]:
        objects = [self.author]
        malware_name = labels[0].replace("-", " ").title()
        malware = Malware(
            name=malware_name,
            is_family=True,
            labels=labels,
            created_by_ref=self.author.id,
            description=f"Infraestructura C2 detectada ({malware_name})",
            allow_custom=True
        )
        objects.append(malware)

        lines = content.splitlines()
        for line in lines:
            if not line.strip(): continue
            try:
                data = json.loads(line)
                result = data.get("result", {})
                
                ip = result.get("ip")
                raw_domain = result.get("C2Server")
                
                # Limpieza del campo C2Server
                clean_domain_candidate = None
                if raw_domain:
                    if isinstance(raw_domain, list) and len(raw_domain) > 0:
                        raw_domain = raw_domain[0]
                    if isinstance(raw_domain, str):
                        pre_clean = raw_domain.split(',')[0]
                        clean_domain_candidate = self._clean_domain(pre_clean)

                # A) Procesar IP principal
                if ip and self._is_public_ip(ip):
                    stix_ip = IPv4Address(
                        value=ip, labels=labels, allow_custom=True, created_by_ref=self.author.id
                    )
                    objects.append(stix_ip)
                    rel = Relationship(
                        relationship_type="related-to", source_ref=stix_ip.id, target_ref=malware.id, created_by_ref=self.author.id, allow_custom=True
                    )
                    objects.append(rel)

                # B) Procesar el C2Server (Lógica corregida)
                if clean_domain_candidate:
                    # 1. Comprobamos si es ESTRUCTURALMENTE una IP (ej: 127.0.0.1 o 8.8.8.8)
                    if self._is_ip_structure(clean_domain_candidate):
                        # Si es una IP, solo la ingestamos si es pública y distinta a la principal
                        if self._is_public_ip(clean_domain_candidate) and clean_domain_candidate != ip:
                            stix_ip_2 = IPv4Address(
                                value=clean_domain_candidate, labels=labels, allow_custom=True, created_by_ref=self.author.id
                            )
                            objects.append(stix_ip_2)
                            rel_ip2 = Relationship(
                                relationship_type="related-to", source_ref=stix_ip_2.id, target_ref=malware.id, created_by_ref=self.author.id, allow_custom=True
                            )
                            objects.append(rel_ip2)
                        # Si es una IP privada (127.0.0.1), NO hacemos nada. NO entramos al 'else'.
                    else:
                        # 2. Si NO es una IP, entonces asumimos que es un Dominio real
                        stix_domain = DomainName(
                            value=clean_domain_candidate, labels=labels, allow_custom=True, created_by_ref=self.author.id
                        )
                        objects.append(stix_domain)
                        rel_d = Relationship(
                            relationship_type="related-to", source_ref=stix_domain.id, target_ref=malware.id, created_by_ref=self.author.id, allow_custom=True
                        )
                        objects.append(rel_d)

            except json.JSONDecodeError:
                continue
            except Exception:
                continue
        return objects

    def process_text_list_url(self, content: str, labels: List[str]) -> List[Any]:
        objects = [self.author]
        lines = content.splitlines()
        for line in lines:
            url = line.strip()
            if not url or url.startswith("#"): continue
            
            stix_url = URL(value=url, labels=labels, allow_custom=True, created_by_ref=self.author.id)
            objects.append(stix_url)
            
            indicator = Indicator(
                pattern=f"[url:value = '{url}']",
                pattern_type="stix",
                name=f"Malicious URL detected ({labels[0]})",
                labels=labels,
                created_by_ref=self.author.id,
                allow_custom=True
            )
            objects.append(indicator)
            
            rel = Relationship(
                relationship_type="based-on", source_ref=indicator.id, target_ref=stix_url.id, created_by_ref=self.author.id, allow_custom=True
            )
            objects.append(rel)
        return objects

    def process_text_list_ip(self, content: str, labels: List[str]) -> List[Any]:
        objects = [self.author]
        lines = content.splitlines()
        for line in lines:
            ip = line.strip()
            if ip and not ip.startswith("#") and self._is_public_ip(ip):
                stix_ip = IPv4Address(value=ip, labels=labels, allow_custom=True, created_by_ref=self.author.id)
                objects.append(stix_ip)
        return objects

    def run(self):
        self.helper.log_info("Iniciando TFG Multi-Feed")
        while True:
            try:
                timestamp = int(time.time())
                now = datetime.fromtimestamp(timestamp, timezone.utc)
                friendly_name = "Ejecución Multi-Feed " + now.strftime("%Y-%m-%d %H:%M:%S")
                
                work_id = self.helper.api.work.initiate_work(self.helper.connect_id, friendly_name)
                feeds = self.get_feeds_config()
                
                for feed in feeds:
                    name = feed.get('name', 'Unknown')
                    url = feed.get('url')
                    parser_type = feed.get('parser')
                    labels = feed.get('labels', [])
                    
                    if not url: continue
                    self.helper.api.work.to_received(work_id, f"Procesando {name}...")
                    
                    content = self.download_data(url)
                    if not content: continue

                    stix_objects = []
                    try:
                        if parser_type == "drb-json":
                            stix_objects = self.process_drb_json(content, labels)
                        elif parser_type == "text-list-url":
                            stix_objects = self.process_text_list_url(content, labels)
                        elif parser_type == "text-list-ip":
                            stix_objects = self.process_text_list_ip(content, labels)
                    except Exception as e:
                        self.helper.log_error(f"Error parseando {name}: {e}")
                        continue
                    
                    if stix_objects:
                        self.helper.log_info(f"Enviando {len(stix_objects)} objetos de {name}...")
                        try:
                            bundle = Bundle(objects=stix_objects, allow_custom=True)
                            self.helper.send_stix2_bundle(bundle.serialize(), update=True, work_id=work_id)
                        except Exception as e:
                             self.helper.log_error(f"Error enviando bundle: {e}")

                self.helper.api.work.to_processed(work_id, "Completado")
                self.helper.log_info(f"Trabajo finalizado.")

            except Exception as e:
                self.helper.log_error(str(e))

            try:
                interval = int(os.environ.get("CONNECTOR_RUN_EVERY", "3600"))
            except ValueError:
                interval = 3600

            self.helper.log_info(f"Durmiendo {interval}s...")
            time.sleep(interval)

if __name__ == "__main__":
    try:
        connector = MultiFeedConnector()
        connector.run()
    except Exception as e:
        print(f"Error fatal: {e}")
        time.sleep(10)
        exit(1)
