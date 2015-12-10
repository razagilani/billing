"""This module should contain subclasses of QuoteParser for specific
suppliers, each one in a separate file.
"""
from .aep import AEPMatrixParser
from .amerigreen import AmerigreenMatrixParser
from .champion import ChampionMatrixParser
from .constellation import ConstellationMatrixParser
from .direct_energy import DirectEnergyMatrixParser
from .liberty import LibertyMatrixParser
from .entrust import EntrustMatrixParser
from .major_energy import MajorEnergyMatrixParser
from .usge import USGEMatrixParser
from .usge_electric import USGEElectricMatrixParser
from .sfe import SFEMatrixParser

# mapping of each supplier's primary key in the database to its QuoteParser
# subclass. each time a subclass is written for a new supplier, add it to
# this dictionary.
CLASSES_FOR_FORMATS = {
    6: AEPMatrixParser,
    11: AmerigreenMatrixParser,
    7: ChampionMatrixParser,
    3: ConstellationMatrixParser,
    8: DirectEnergyMatrixParser,
    1: LibertyMatrixParser,
    2: EntrustMatrixParser,
    10: MajorEnergyMatrixParser,
    9: SFEMatrixParser,
    4: USGEMatrixParser,
    5: USGEElectricMatrixParser,
}
