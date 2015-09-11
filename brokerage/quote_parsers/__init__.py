"""This module should contain subclasses of QuoteParser for specific
suppliers, each one in a separate file.
"""
from .aep import AEPMatrixParser
from .amerigreen import AmerigreenMatrixParser
from .champion import ChampionMatrixParser
from .constellation import ConstellationMatrixParser
from .direct_energy import DirectEnergyMatrixParser
from .liberty import LibertyMatrixParser
from .major_energy import MajorEnergyMatrixParser
from .usge import USGEMatrixParser

# mapping of each supplier's primary key in the database to its QuoteParser
# subclass. each time a subclass is written for a new supplier, add it to
# this dictionary.
CLASSES_FOR_SUPPLIERS = {
    95: AEPMatrixParser,
    125: AmerigreenMatrixParser,
    928: ChampionMatrixParser,
    103: ConstellationMatrixParser,
    14: DirectEnergyMatrixParser,
    93: LibertyMatrixParser,
    78: MajorEnergyMatrixParser,
    199: USGEMatrixParser,
}

