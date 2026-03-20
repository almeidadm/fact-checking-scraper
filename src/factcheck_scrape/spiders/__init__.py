from .afp_checamos import AfpChecamosSpider
from .agencia_lupa import AgenciaLupaSpider
from .aosfatos import AosFatosSpider
from .boatos_org import BoatosOrgSpider
from .e_farsas import EFarsasSpider
from .estadao_verifica import EstadaoVerificaSpider
from .g1_fato_ou_fake import G1FatoOuFakeSpider
from .observador import ObservadorSpider
from .poligrafo import PoligrafoSpider
from .projeto_comprova import ProjetoComprovaSpider
from .publico import PublicoSpider
from .reuters_fact_check import ReutersFactCheckSpider
from .uol_confere import UolConfereSpider

SPIDER_CLASSES = [
    ReutersFactCheckSpider,
    EstadaoVerificaSpider,
    G1FatoOuFakeSpider,
    AosFatosSpider,
    AgenciaLupaSpider,
    AfpChecamosSpider,
    BoatosOrgSpider,
    EFarsasSpider,
    ObservadorSpider,
    PoligrafoSpider,
    PublicoSpider,
    UolConfereSpider,
    ProjetoComprovaSpider,
]

__all__ = [
    "AosFatosSpider",
    "AfpChecamosSpider",
    "AgenciaLupaSpider",
    "BoatosOrgSpider",
    "EFarsasSpider",
    "EstadaoVerificaSpider",
    "G1FatoOuFakeSpider",
    "ObservadorSpider",
    "PoligrafoSpider",
    "ProjetoComprovaSpider",
    "PublicoSpider",
    "ReutersFactCheckSpider",
    "UolConfereSpider",
    "SPIDER_CLASSES",
]
