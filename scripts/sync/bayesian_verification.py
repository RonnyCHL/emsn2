#!/usr/bin/env python3
"""
EMSN 2.0 - Bayesian Verification Model

Berekent de waarschijnlijkheid dat een vogeldetectie correct is op basis van:
1. Prior probability: Hoe waarschijnlijk is deze soort op deze locatie?
2. Dual detection likelihood: Wordt de vogel op beide stations gedetecteerd?
3. Confidence consistency: Hoe consistent zijn de confidence scores?
4. Temporal pattern: Past de detectie in het normale dagpatroon?
5. Rarity factor: Zeldzame vogels hebben meer bewijs nodig

Bayes' Theorem: P(correct|evidence) = P(evidence|correct) * P(correct) / P(evidence)
"""

import psycopg2
import math
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
import json


class BayesianVerificationModel:
    """
    Bayesiaans model voor verificatie van vogeldetecties.

    Het model berekent P(correct|evidence) waarbij:
    - P(correct) = prior probability gebaseerd op historische data
    - P(evidence|correct) = likelihood van de waargenomen evidence als de detectie correct is
    - P(evidence) = totale probability van de evidence (normalisatiefactor)
    """

    def __init__(self, pg_config_or_conn, logger=None):
        """
        Initialize the Bayesian model.

        Args:
            pg_config_or_conn: Either a dict with PostgreSQL config, or an existing connection
            logger: Optional logger instance for output
        """
        # Accept either a config dict or an existing connection
        if isinstance(pg_config_or_conn, dict):
            self.pg_config = pg_config_or_conn
            self.conn = None
            self.owns_connection = True
        else:
            # Assume it's a connection object
            self.pg_config = None
            self.conn = pg_config_or_conn
            self.owns_connection = False

        self.logger = logger
        self.species_stats = {}  # Renamed from species_stats for clarity

        # Model parameters (kunnen worden getuned)
        self.params = {
            # Dual detection boost - hoeveel betrouwbaarder is een dual detection?
            'dual_detection_multiplier': 3.0,

            # Tijd decay - hoe snel neemt de dual detection waarde af met tijd?
            'time_decay_halflife': 15.0,  # seconden

            # Confidence thresholds
            'min_confidence': 0.6,
            'high_confidence': 0.85,

            # Prior bounds
            'min_prior': 0.05,  # Minimale prior voor zeldzame soorten
            'max_prior': 0.95,  # Maximale prior voor veelvoorkomende soorten

            # Single station penalty voor soorten die normaal dual zijn
            'single_station_penalty': 0.7,

            # Rarity penalty exponent
            'rarity_exponent': 0.5,
        }


    def connect(self):
        """Connect to PostgreSQL database"""
        if self.pg_config:
            self.conn = psycopg2.connect(**self.pg_config)
        return True

    def close(self):
        """Close database connection (only if we own it)"""
        if self.conn and self.owns_connection:
            self.conn.close()

    def _log(self, message):
        """Log a message if logger is available"""
        if self.logger:
            self.logger.info(message)
        else:
            print(message)

    def load_species_statistics(self):
        """
        Laad statistieken per soort uit de database.
        Dit vormt de basis voor de prior probabilities.
        """
        cursor = self.conn.cursor()

        query = """
            SELECT
                species,
                common_name,
                COUNT(*) as total_detections,
                SUM(CASE WHEN station='zolder' THEN 1 ELSE 0 END) as zolder_count,
                SUM(CASE WHEN station='berging' THEN 1 ELSE 0 END) as berging_count,
                SUM(CASE WHEN dual_detection THEN 1 ELSE 0 END) as dual_count,
                AVG(confidence) as avg_confidence,
                STDDEV(confidence) as stddev_confidence,
                AVG(CASE WHEN dual_detection THEN confidence ELSE NULL END) as avg_dual_confidence,
                AVG(CASE WHEN NOT dual_detection THEN confidence ELSE NULL END) as avg_single_confidence
            FROM bird_detections
            GROUP BY species, common_name
        """

        cursor.execute(query)

        for row in cursor.fetchall():
            species = row[0]
            self.species_stats[species] = {
                'common_name': row[1],
                'total_detections': row[2],
                'zolder_count': row[3],
                'berging_count': row[4],
                'dual_count': row[5],
                'dual_rate': row[5] / row[2] if row[2] > 0 else 0,
                'avg_confidence': float(row[6]) if row[6] else 0.75,
                'stddev_confidence': float(row[7]) if row[7] else 0.1,
                'avg_dual_confidence': float(row[8]) if row[8] else 0.8,
                'avg_single_confidence': float(row[9]) if row[9] else 0.75,
                'presence_both_stations': row[3] > 0 and row[4] > 0,
            }

        return len(self.species_stats)

    def calculate_prior(self, species: str, station: str) -> float:
        """
        Bereken de prior probability P(correct) voor een soort op een station.

        Factoren:
        - Frequentie van de soort in de dataset (veelvoorkomend = hogere prior)
        - Aanwezigheid op beide stations (beide = hogere prior)
        - Historische confidence voor deze soort
        """
        if species not in self.species_stats:
            # Onbekende soort - lage prior
            return self.params['min_prior']

        stats = self.species_stats[species]

        # Base prior op frequentie (log schaal om extreme waarden te dempen)
        total = stats['total_detections']
        if total == 0:
            return self.params['min_prior']

        # Log-frequentie normalisatie
        max_detections = max(s['total_detections'] for s in self.species_stats.values())
        freq_factor = math.log(1 + total) / math.log(1 + max_detections)

        # Station-specifieke aanpassing
        station_count = stats['zolder_count'] if station == 'zolder' else stats['berging_count']
        station_factor = station_count / total if total > 0 else 0.5

        # Dual detection rate boost - soorten met hoge dual rate zijn betrouwbaarder
        dual_boost = 1.0 + (stats['dual_rate'] * 0.5)

        # Historische confidence factor
        conf_factor = stats['avg_confidence']

        # Combineer factoren
        prior = freq_factor * station_factor * dual_boost * conf_factor

        # Clamp to bounds
        prior = max(self.params['min_prior'], min(self.params['max_prior'], prior))

        return prior

    def calculate_rarity_factor(self, species: str) -> float:
        """
        Bereken zeldzaamheidsfactor.
        Zeldzame vogels hebben een lagere base probability en vereisen sterker bewijs.
        """
        if species not in self.species_stats:
            return 0.3  # Onbekend = potentieel zeldzaam

        stats = self.species_stats[species]
        total = stats['total_detections']

        # Zeldzaamheid op log schaal
        max_detections = max(s['total_detections'] for s in self.species_stats.values())

        if max_detections == 0:
            return 0.5

        # Rarity = 1 voor veelvoorkomend, lager voor zeldzaam
        rarity = (math.log(1 + total) / math.log(1 + max_detections)) ** self.params['rarity_exponent']

        return max(0.1, rarity)

    def calculate_dual_detection_likelihood(
        self,
        is_dual: bool,
        time_diff_seconds: Optional[float],
        conf_zolder: float,
        conf_berging: float,
        species: str
    ) -> float:
        """
        Bereken de likelihood P(evidence|correct) gebaseerd op dual detection.

        Als beide stations dezelfde vogel detecteren binnen een kort tijdsvenster,
        is de kans veel groter dat de detectie correct is.
        """
        if not is_dual:
            # Single detection - check of deze soort normaal dual zou moeten zijn
            if species in self.species_stats:
                expected_dual_rate = self.species_stats[species]['dual_rate']
                if expected_dual_rate > 0.2:
                    # Deze soort wordt vaak dual gedetecteerd, single is verdacht
                    return self.params['single_station_penalty']
            return 1.0  # Neutraal voor soorten die zelden dual zijn

        # Dual detection - bereken likelihood boost

        # 1. Time decay: kortere tijd = hogere likelihood
        if time_diff_seconds is not None:
            time_factor = math.exp(-time_diff_seconds / self.params['time_decay_halflife'] * math.log(2))
        else:
            time_factor = 0.5

        # 2. Confidence agreement: vergelijkbare confidence = hogere likelihood
        conf_diff = abs(conf_zolder - conf_berging)
        conf_agreement = 1.0 - (conf_diff * 0.5)  # Max 50% penalty voor grote verschillen

        # 3. Average confidence level
        avg_conf = (conf_zolder + conf_berging) / 2
        conf_level = avg_conf / self.params['high_confidence']
        conf_level = min(1.2, conf_level)  # Cap bonus at 20%

        # Combineer factoren met dual detection multiplier
        likelihood = self.params['dual_detection_multiplier'] * time_factor * conf_agreement * conf_level

        return likelihood

    def calculate_confidence_likelihood(self, confidence: float, species: str) -> float:
        """
        Bereken likelihood gebaseerd op hoe de confidence zich verhoudt tot
        de verwachte confidence voor deze soort.
        """
        if species not in self.species_stats:
            # Onbekende soort - gebruik confidence direct
            return confidence

        stats = self.species_stats[species]
        expected_conf = stats['avg_confidence']
        stddev = stats['stddev_confidence'] or 0.1

        # Z-score: hoeveel standaarddeviaties van het gemiddelde?
        z_score = (confidence - expected_conf) / stddev

        # Hogere confidence dan verwacht = boost, lager = penalty
        # Gebruik sigmoid-achtige functie
        likelihood = 1.0 / (1.0 + math.exp(-z_score))

        # Scale to reasonable range [0.5, 1.5]
        likelihood = 0.5 + likelihood

        return likelihood

    def calculate_posterior(
        self,
        species: str,
        station: str,
        confidence: float,
        is_dual: bool = False,
        time_diff_seconds: Optional[float] = None,
        dual_confidence: Optional[float] = None
    ) -> Dict:
        """
        Bereken de posterior probability P(correct|evidence) met Bayes' theorem.

        Returns een dictionary met:
        - posterior: De finale waarschijnlijkheid dat de detectie correct is
        - prior: De a priori waarschijnlijkheid
        - likelihood: De gecombineerde likelihood
        - components: Breakdown van de verschillende factoren
        """

        # 1. Prior
        prior = self.calculate_prior(species, station)

        # 2. Rarity factor
        rarity = self.calculate_rarity_factor(species)

        # 3. Dual detection likelihood
        if is_dual and dual_confidence is not None:
            dual_likelihood = self.calculate_dual_detection_likelihood(
                is_dual=True,
                time_diff_seconds=time_diff_seconds,
                conf_zolder=confidence if station == 'zolder' else dual_confidence,
                conf_berging=dual_confidence if station == 'zolder' else confidence,
                species=species
            )
        else:
            dual_likelihood = self.calculate_dual_detection_likelihood(
                is_dual=False,
                time_diff_seconds=None,
                conf_zolder=confidence,
                conf_berging=0,
                species=species
            )

        # 4. Confidence likelihood
        conf_likelihood = self.calculate_confidence_likelihood(confidence, species)

        # 5. Combine likelihoods
        combined_likelihood = dual_likelihood * conf_likelihood * rarity

        # 6. Bayes' theorem: P(correct|evidence) = P(evidence|correct) * P(correct) / P(evidence)
        # We approximeren P(evidence) door te normaliseren

        # Numerator: P(evidence|correct) * P(correct)
        numerator = combined_likelihood * prior

        # P(evidence|incorrect) * P(incorrect)
        # Assumptie: als incorrect, is de likelihood veel lager
        false_positive_likelihood = 0.1  # Base false positive rate
        denominator_false = false_positive_likelihood * (1 - prior)

        # Normalize
        denominator = numerator + denominator_false

        if denominator == 0:
            posterior = 0.5
        else:
            posterior = numerator / denominator

        # Clamp to [0, 1]
        posterior = max(0.0, min(1.0, posterior))

        return {
            'posterior': round(posterior, 4),
            'prior': round(prior, 4),
            'likelihood': round(combined_likelihood, 4),
            'components': {
                'rarity_factor': round(rarity, 4),
                'dual_likelihood': round(dual_likelihood, 4),
                'confidence_likelihood': round(conf_likelihood, 4),
            },
            'is_dual': is_dual,
            'confidence': confidence,
        }

    def calculate_dual_verification_score(
        self,
        species: str,
        zolder_confidence: float,
        berging_confidence: float,
        time_diff_seconds: float
    ) -> Dict:
        """
        Bereken een verificatiescore specifiek voor dual detections.

        Dit is de score die wordt opgeslagen in de dual_detections tabel.
        """

        # Calculate for both stations
        zolder_result = self.calculate_posterior(
            species=species,
            station='zolder',
            confidence=zolder_confidence,
            is_dual=True,
            time_diff_seconds=time_diff_seconds,
            dual_confidence=berging_confidence
        )

        berging_result = self.calculate_posterior(
            species=species,
            station='berging',
            confidence=berging_confidence,
            is_dual=True,
            time_diff_seconds=time_diff_seconds,
            dual_confidence=zolder_confidence
        )

        # Combined verification score (geometric mean of posteriors)
        combined_posterior = math.sqrt(zolder_result['posterior'] * berging_result['posterior'])

        # Additional factors for dual-specific score

        # Confidence agreement bonus
        conf_diff = abs(zolder_confidence - berging_confidence)
        agreement_factor = 1.0 - (conf_diff * 0.3)

        # Time proximity bonus
        time_factor = math.exp(-time_diff_seconds / 30.0 * math.log(2))

        # Final verification score
        verification_score = combined_posterior * agreement_factor * (0.7 + 0.3 * time_factor)
        verification_score = max(0.0, min(1.0, verification_score))

        return {
            'verification_score': round(verification_score, 4),
            'combined_posterior': round(combined_posterior, 4),
            'zolder_posterior': zolder_result['posterior'],
            'berging_posterior': berging_result['posterior'],
            'agreement_factor': round(agreement_factor, 4),
            'time_factor': round(time_factor, 4),
            'components': {
                'zolder': zolder_result,
                'berging': berging_result,
            }
        }


# Convenience function for use in dual_detection_sync.py
def calculate_bayesian_verification_score(
    pg_config: Dict,
    species: str,
    zolder_confidence: float,
    berging_confidence: float,
    time_diff_seconds: float,
    species_stats: Optional[Dict] = None
) -> float:
    """
    Standalone function to calculate Bayesian verification score.

    Can be called from dual_detection_sync.py with a pre-loaded cache.
    """
    model = BayesianVerificationModel(pg_config)

    if species_stats:
        model.species_stats = species_stats
    else:
        model.connect()
        model.load_species_statistics()
        model.close()

    result = model.calculate_dual_verification_score(
        species=species,
        zolder_confidence=zolder_confidence,
        berging_confidence=berging_confidence,
        time_diff_seconds=time_diff_seconds
    )

    return result['verification_score']


# Test function
if __name__ == "__main__":
    import os
    import sys
    from pathlib import Path

    # Import core modules for test
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from core.config import get_postgres_config

    # Test configuration (from core module)
    PG_CONFIG = get_postgres_config()

    print("=" * 70)
    print("EMSN Bayesian Verification Model - Test")
    print("=" * 70)

    model = BayesianVerificationModel(PG_CONFIG)
    model.connect()

    num_species = model.load_species_statistics()
    print(f"\nLoaded statistics for {num_species} species")

    # Test cases
    test_cases = [
        # (species, zolder_conf, berging_conf, time_diff, description)
        ("Pica pica", 0.92, 0.88, 2, "Ekster - hoge conf, snelle dual"),
        ("Pica pica", 0.75, 0.72, 25, "Ekster - medium conf, langzame dual"),
        ("Erithacus rubecula", 0.85, 0.82, 5, "Roodborst - goede dual"),
        ("Troglodytes troglodytes", 0.90, 0.88, 1, "Winterkoning - excellente dual"),
        ("Anser brachyrhynchus", 0.78, 0.75, 10, "Kleine Rietgans - alleen berging normaal"),
        ("Ara macao", 0.72, 0.70, 15, "Geelvleugelara - verdachte soort"),
    ]

    print("\n" + "-" * 70)
    print("Test Cases:")
    print("-" * 70)

    for species, z_conf, b_conf, time_diff, desc in test_cases:
        result = model.calculate_dual_verification_score(
            species=species,
            zolder_confidence=z_conf,
            berging_confidence=b_conf,
            time_diff_seconds=time_diff
        )

        print(f"\n{desc}")
        print(f"  Species: {species}")
        print(f"  Confidence: zolder={z_conf}, berging={b_conf}")
        print(f"  Time diff: {time_diff}s")
        print(f"  -> Verification Score: {result['verification_score']:.3f}")
        print(f"     Combined posterior: {result['combined_posterior']:.3f}")
        print(f"     Agreement factor: {result['agreement_factor']:.3f}")
        print(f"     Time factor: {result['time_factor']:.3f}")

    # Test single detection
    print("\n" + "-" * 70)
    print("Single Detection Tests:")
    print("-" * 70)

    single_tests = [
        ("Pica pica", "zolder", 0.85, "Ekster single - normaal dual soort"),
        ("Pica pica", "berging", 0.92, "Ekster single - hoge confidence"),
        ("Anser brachyrhynchus", "berging", 0.80, "Kleine Rietgans - alleen berging normaal"),
    ]

    for species, station, conf, desc in single_tests:
        result = model.calculate_posterior(
            species=species,
            station=station,
            confidence=conf,
            is_dual=False
        )

        print(f"\n{desc}")
        print(f"  Species: {species}, Station: {station}, Conf: {conf}")
        print(f"  -> Posterior: {result['posterior']:.3f}")
        print(f"     Prior: {result['prior']:.3f}")
        print(f"     Likelihood: {result['likelihood']:.3f}")

    model.close()
    print("\n" + "=" * 70)
    print("Test completed")
    print("=" * 70)
