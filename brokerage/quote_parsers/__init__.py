"""This module should contain subclasses of QuoteParser for specific
suppliers, each one in a separate file.
"""
from .aep import AEPMatrixParser
from .amerigreen import AmerigreenMatrixParser
from .champion import ChampionMatrixParser
from .constellation import ConstellationMatrixParser
from .direct_energy import DirectEnergyMatrixParser
from .usge import USGEMatrixParser

# mapping of each supplier's primary keys in database to its QuoteParser
# subclass. each time a subclass is written for a new supplier, add it to
# this dictionary.
CLASSES_FOR_SUPPLIERS = {
    14: DirectEnergyMatrixParser,
    95: AEPMatrixParser,
    199: USGEMatrixParser,
    928: ChampionMatrixParser,
    125: AmerigreenMatrixParser,
}

