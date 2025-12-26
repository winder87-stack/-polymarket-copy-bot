"""
Automatic Wallet Selection System
=================================

Intelligent portfolio construction and wallet selection based on quality scores.

Features:
- Top-N wallet selection by quality score
- Portfolio diversification with correlation constraints
- Risk-budgeted allocation by wallet quality
- Automatic wallet rotation based on performance
- Manual override capabilities with audit trails
- Scenario-based portfolio optimization
"""

import asyncio
import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.spatial.distance import pdist, squareform
from sklearn.cluster import KMeans

from core.real_time_scorer import RealTimeScoringEngine

logger = logging.getLogger(__name__)


class AutomaticWalletSelector:
    """
    Automatic wallet selection and portfolio construction system.

    Uses quality scores to intelligently select and allocate capital
    across wallets while maintaining diversification and risk constraints.
    """

    def __init__(self, real_time_scorer: RealTimeScoringEngine):
        self.real_time_scorer = real_time_scorer

        # Selection parameters
        self.selection_params = {
            "default_top_n": 15,                  # Default number of wallets to select
            "min_quality_score": 50,              # Minimum quality score for selection
            "max_wallet_allocation": 0.15,        # Maximum allocation per wallet (15%)
            "min_wallet_allocation": 0.02,        # Minimum allocation per wallet (2%)
            "max_correlation_threshold": 0.7,     # Maximum allowed correlation between wallets
            "diversification_clusters": 5,        # Number of diversification clusters
            "rotation_threshold": 0.15,           # Score change threshold for rotation (15%)
            "rotation_cooldown_days": 7,          # Minimum days between rotations
            "risk_budget_tiers": 3,               # Number of risk budget tiers
            "rebalancing_threshold": 0.05,        # 5% deviation triggers rebalancing
            "scenario_stress_tests": 100,         # Number of stress test scenarios
            "performance_lookback_days": 30,     # Days for performance evaluation
            "manual_override_expiry_hours": 24,   # Manual overrides expire after 24 hours
        }

        # Portfolio state
        self.current_portfolio: Dict[str, Dict[str, Any]] = {}
        self.portfolio_history: List[Dict[str, Any]] = []
        self.rotation_history: List[Dict[str, Any]] = []

        # Manual overrides
        self.manual_overrides: Dict[str, Dict[str, Any]] = {}
        self.override_audit_log: List[Dict[str, Any]] = []

        # Correlation and clustering data
        self.wallet_correlations: Dict[str, Dict[str, float]] = {}
        self.wallet_clusters: Dict[str, int] = {}

        # Performance tracking
        self.selection_performance: Dict[str, Any] = {}
        self.backtest_results: List[Dict[str, Any]] = []

        logger.info("🎯 Automatic wallet selector initialized")

    async def select_optimal_portfolio(
        self,
        available_wallets: List[Dict[str, Any]],
        total_capital: float,
        selection_criteria: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Select optimal wallet portfolio based on quality scores and constraints.

        Args:
            available_wallets: List of wallet information dictionaries
            total_capital: Total capital available for allocation
            selection_criteria: Optional custom selection criteria

        Returns:
            Optimal portfolio allocation with selection rationale
        """

        try:
            # Apply default selection criteria if none provided
            criteria = selection_criteria or self._get_default_selection_criteria()

            # Get real-time quality scores for all available wallets
            wallet_scores = await self._get_wallet_quality_scores(available_wallets)

            # Filter wallets meeting minimum criteria
            qualified_wallets = self._filter_qualified_wallets(wallet_scores, criteria)

            if len(qualified_wallets) < criteria["min_wallet_count"]:
                return self._create_insufficient_wallets_response(qualified_wallets, criteria)

            # Select top wallets by quality score
            top_wallets = self._select_top_wallets(qualified_wallets, criteria)

            # Apply diversification constraints
            diversified_portfolio = await self._apply_diversification_constraints(top_wallets, criteria)

            # Calculate risk-budgeted allocations
            risk_budgeted_allocations = self._calculate_risk_budgeted_allocations(
                diversified_portfolio, total_capital, criteria
            )

            # Apply manual overrides
            final_allocations = self._apply_manual_overrides(risk_budgeted_allocations)

            # Generate portfolio summary
            portfolio_summary = self._generate_portfolio_summary(
                final_allocations, qualified_wallets, criteria
            )

            # Store portfolio state
            self._store_portfolio_state(final_allocations, criteria)

            logger.info(f"✅ Selected portfolio with {len(final_allocations)} wallets, total allocation: ${sum(a['allocated_capital'] for a in final_allocations.values()):.2f}")

            return portfolio_summary

        except Exception as e:
            logger.error(f"Error selecting optimal portfolio: {e}")
            return {
                "error": str(e),
                "selection_timestamp": datetime.now().isoformat()
            }

    def _get_default_selection_criteria(self) -> Dict[str, Any]:
        """Get default selection criteria."""

        return {
            "top_n_wallets": self.selection_params["default_top_n"],
            "min_quality_score": self.selection_params["min_quality_score"],
            "min_wallet_count": 5,
            "max_wallet_count": 20,
            "diversification_required": True,
            "risk_budgeting_enabled": True,
            "correlation_constraint": self.selection_params["max_correlation_threshold"],
            "cluster_diversification": True,
            "quality_weighted_allocation": True
        }

    async def _get_wallet_quality_scores(self, wallets: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Get real-time quality scores for all wallets."""

        wallet_scores = {}

        for wallet in wallets:
            wallet_address = wallet["address"]

            # Get real-time score
            score_data = await self.real_time_scorer.get_real_time_score(wallet_address)

            if "current_score" in score_data and score_data["current_score"] is not None:
                wallet_scores[wallet_address] = {
                    "score": score_data["current_score"],
                    "confidence": score_data.get("confidence_intervals", {}),
                    "stability": score_data.get("stability_metrics", {}),
                    "wallet_info": wallet,
                    "last_update": score_data.get("last_update"),
                    "alerts": score_data.get("alerts", [])
                }
            else:
                # Use fallback scoring for wallets without real-time data
                fallback_score = await self._calculate_fallback_score(wallet)
                wallet_scores[wallet_address] = {
                    "score": fallback_score,
                    "confidence": {"confidence_level": 0.5},
                    "stability": {"stability_score": 0.5},
                    "wallet_info": wallet,
                    "fallback": True
                }

        return wallet_scores

    async def _calculate_fallback_score(self, wallet: Dict[str, Any]) -> float:
        """Calculate fallback quality score for wallets without real-time data."""

        # Simple fallback based on wallet type and basic metrics
        wallet_type = wallet.get("classification", "unknown")
        confidence = wallet.get("confidence_score", 0.5)

        base_scores = {
            "market_maker": 65,
            "directional_trader": 60,
            "arbitrage_trader": 70,
            "high_frequency_trader": 55,
            "mixed_trader": 58,
            "unknown": 50
        }

        base_score = base_scores.get(wallet_type, 50)
        adjusted_score = base_score * confidence

        return adjusted_score

    def _filter_qualified_wallets(
        self,
        wallet_scores: Dict[str, Dict[str, Any]],
        criteria: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Filter wallets that meet minimum qualification criteria."""

        qualified = []

        for wallet_address, score_data in wallet_scores.items():
            score = score_data["score"]
            confidence = score_data["confidence"].get("confidence_level", 0.5)

            # Apply qualification filters
            if score >= criteria["min_quality_score"] and confidence >= 0.3:
                # Check for active alerts that might disqualify
                disqualifying_alerts = [
                    alert for alert in score_data.get("alerts", [])
                    if alert.get("severity") in ["high", "critical"]
                ]

                if not disqualifying_alerts:
                    qualified_wallet = {
                        "address": wallet_address,
                        "quality_score": score,
                        "confidence": confidence,
                        "stability_score": score_data["stability"].get("stability_score", 0.5),
                        "wallet_info": score_data["wallet_info"],
                        "alerts": score_data.get("alerts", []),
                        "fallback": score_data.get("fallback", False)
                    }
                    qualified.append(qualified_wallet)

        # Sort by quality score (descending)
        qualified.sort(key=lambda x: x["quality_score"], reverse=True)

        return qualified

    def _select_top_wallets(self, qualified_wallets: List[Dict[str, Any]], criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Select top N wallets by quality score."""

        top_n = criteria["top_n_wallets"]
        max_count = criteria["max_wallet_count"]

        # Select top wallets
        selected = qualified_wallets[:min(top_n, max_count, len(qualified_wallets))]

        return selected

    async def _apply_diversification_constraints(
        self,
        selected_wallets: List[Dict[str, Any]],
        criteria: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Apply diversification constraints to selected wallets."""

        if not criteria.get("diversification_required", False) or len(selected_wallets) <= 3:
            return selected_wallets

        try:
            # Update wallet correlations
            await self._update_wallet_correlations(selected_wallets)

            # Apply correlation-based filtering
            correlation_filtered = self._apply_correlation_filtering(selected_wallets, criteria)

            # Apply cluster-based diversification if enabled
            if criteria.get("cluster_diversification", False):
                cluster_diversified = await self._apply_cluster_diversification(correlation_filtered, criteria)
                return cluster_diversified

            return correlation_filtered

        except Exception as e:
            logger.error(f"Error applying diversification constraints: {e}")
            return selected_wallets  # Return original selection on error

    async def _update_wallet_correlations(self, wallets: List[Dict[str, Any]]):
        """Update correlation matrix for wallet diversification."""

        try:
            wallet_addresses = [w["address"] for w in wallets]

            # Calculate or retrieve correlations
            # In practice, this would use historical return correlations
            for i, wallet1 in enumerate(wallet_addresses):
                for j, wallet2 in enumerate(wallet_addresses):
                    if i != j:
                        # Simplified correlation calculation
                        # In practice, would use actual return series
                        correlation = 0.1 + 0.1 * np.random.random()  # Placeholder
                        self.wallet_correlations.setdefault(wallet1, {})[wallet2] = correlation

        except Exception as e:
            logger.error(f"Error updating wallet correlations: {e}")

    def _apply_correlation_filtering(
        self,
        wallets: List[Dict[str, Any]],
        criteria: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Filter wallets based on correlation constraints."""

        max_correlation = criteria["correlation_constraint"]
        filtered_wallets = []

        for wallet in wallets:
            wallet_address = wallet["address"]

            # Check correlation with already selected wallets
            correlations = [
                self.wallet_correlations.get(wallet_address, {}).get(selected["address"], 0)
                for selected in filtered_wallets
            ]

            if not correlations or max(correlations) <= max_correlation:
                filtered_wallets.append(wallet)

        return filtered_wallets

    async def _apply_cluster_diversification(
        self,
        wallets: List[Dict[str, Any]],
        criteria: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Apply cluster-based diversification to ensure broad coverage."""

        try:
            if len(wallets) <= criteria.get("diversification_clusters", 3):
                return wallets

            # Create feature vectors for clustering
            # Features: quality_score, stability_score, wallet_type, etc.
            feature_vectors = []

            for wallet in wallets:
                features = [
                    wallet["quality_score"] / 100,  # Normalize to 0-1
                    wallet["stability_score"],
                    wallet["confidence"],
                    len(wallet.get("alerts", [])),  # Number of alerts (lower is better)
                ]

                # Add wallet type encoding (simplified)
                wallet_type = wallet["wallet_info"].get("classification", "unknown")
                type_features = self._encode_wallet_type(wallet_type)
                features.extend(type_features)

                feature_vectors.append(features)

            if not feature_vectors:
                return wallets

            # Perform clustering
            n_clusters = min(criteria["diversification_clusters"], len(wallets))
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            clusters = kmeans.fit_predict(feature_vectors)

            # Select best wallet from each cluster
            cluster_best = {}
            for i, wallet in enumerate(wallets):
                cluster_id = clusters[i]
                if cluster_id not in cluster_best or wallet["quality_score"] > cluster_best[cluster_id]["quality_score"]:
                    cluster_best[cluster_id] = wallet

            # Return one wallet per cluster
            diversified_wallets = list(cluster_best.values())

            # Sort by quality score
            diversified_wallets.sort(key=lambda x: x["quality_score"], reverse=True)

            return diversified_wallets

        except Exception as e:
            logger.error(f"Error applying cluster diversification: {e}")
            return wallets

    def _encode_wallet_type(self, wallet_type: str) -> List[int]:
        """Encode wallet type as binary features."""

        types = ["market_maker", "directional_trader", "arbitrage_trader", "high_frequency_trader", "mixed_trader"]
        encoding = [1 if t == wallet_type else 0 for t in types]

        return encoding

    def _calculate_risk_budgeted_allocations(
        self,
        wallets: List[Dict[str, Any]],
        total_capital: float,
        criteria: Dict[str, Any]
    ) -> Dict[str, float]:
        """Calculate risk-budgeted capital allocations."""

        if not criteria.get("risk_budgeting_enabled", False):
            # Equal weight allocation
            equal_weight = total_capital / len(wallets)
            return {wallet["address"]: equal_weight for wallet in wallets}

        try:
            # Quality-weighted allocation with risk constraints
            if criteria.get("quality_weighted_allocation", True):
                allocations = self._quality_weighted_allocation(wallets, total_capital, criteria)
            else:
                allocations = self._equal_weight_allocation(wallets, total_capital)

            # Apply position limits
            allocations = self._apply_position_limits(allocations, total_capital)

            return allocations

        except Exception as e:
            logger.error(f"Error calculating risk-budgeted allocations: {e}")
            # Fallback to equal weight
            return self._equal_weight_allocation(wallets, total_capital)

    def _quality_weighted_allocation(
        self,
        wallets: List[Dict[str, Any]],
        total_capital: float,
        criteria: Dict[str, Any]
    ) -> Dict[str, float]:
        """Allocate capital based on quality scores with risk adjustments."""

        # Extract scores and apply risk adjustments
        wallet_data = []
        for wallet in wallets:
            quality_score = wallet["quality_score"]
            stability_score = wallet["stability_score"]
            confidence = wallet["confidence"]

            # Risk-adjusted weight (higher quality and stability = higher weight)
            risk_adjusted_score = quality_score * stability_score * confidence

            wallet_data.append({
                "address": wallet["address"],
                "score": risk_adjusted_score,
                "quality_score": quality_score
            })

        # Sort by risk-adjusted score
        wallet_data.sort(key=lambda x: x["score"], reverse=True)

        # Apply tiered allocation (top tier gets more allocation)
        n_tiers = self.selection_params["risk_budget_tiers"]
        tier_size = max(1, len(wallet_data) // n_tiers)

        allocations = {}
        remaining_capital = total_capital

        for tier in range(n_tiers):
            start_idx = tier * tier_size
            end_idx = min((tier + 1) * tier_size, len(wallet_data))

            tier_wallets = wallet_data[start_idx:end_idx]

            if not tier_wallets:
                continue

            # Tier allocation weights (higher tiers get more)
            tier_weights = [1.5, 1.2, 1.0]  # Top tier gets 1.5x base allocation
            tier_multiplier = tier_weights[min(tier, len(tier_weights) - 1)]

            # Allocate within tier
            tier_total_score = sum(w["score"] for w in tier_wallets)
            tier_capital = min(remaining_capital, total_capital * (0.6 / (tier + 1)))  # Decreasing allocation per tier

            for wallet in tier_wallets:
                if tier_total_score > 0:
                    weight = (wallet["score"] / tier_total_score) * tier_multiplier
                    allocation = tier_capital * weight
                    allocations[wallet["address"]] = allocation

            remaining_capital -= sum(allocations.get(w["address"], 0) for w in tier_wallets)

        return allocations

    def _equal_weight_allocation(self, wallets: List[Dict[str, Any]], total_capital: float) -> Dict[str, float]:
        """Simple equal weight allocation."""

        equal_allocation = total_capital / len(wallets)
        return {wallet["address"]: equal_allocation for wallet in wallets}

    def _apply_position_limits(self, allocations: Dict[str, float], total_capital: float) -> Dict[str, float]:
        """Apply minimum and maximum position limits."""

        min_allocation = total_capital * self.selection_params["min_wallet_allocation"]
        max_allocation = total_capital * self.selection_params["max_wallet_allocation"]

        adjusted_allocations = {}
        total_adjusted = 0

        # Apply limits
        for wallet_address, allocation in allocations.items():
            adjusted_allocation = max(min_allocation, min(max_allocation, allocation))
            adjusted_allocations[wallet_address] = adjusted_allocation
            total_adjusted += adjusted_allocation

        # Renormalize if total exceeds capital (due to minimum allocations)
        if total_adjusted > total_capital:
            scale_factor = total_capital / total_adjusted
            adjusted_allocations = {k: v * scale_factor for k, v in adjusted_allocations.items()}

        return adjusted_allocations

    def _apply_manual_overrides(self, allocations: Dict[str, float]) -> Dict[str, float]:
        """Apply any active manual overrides to allocations."""

        adjusted_allocations = allocations.copy()

        # Check for active overrides
        current_time = datetime.now()

        for wallet_address, override_data in self.manual_overrides.items():
            expiry_time = datetime.fromisoformat(override_data["expiry_time"])

            if current_time < expiry_time:
                override_type = override_data["override_type"]
                override_value = override_data["override_value"]

                if override_type == "force_include":
                    if wallet_address not in adjusted_allocations:
                        # Add wallet with specified allocation
                        adjusted_allocations[wallet_address] = override_value

                elif override_type == "force_exclude":
                    if wallet_address in adjusted_allocations:
                        del adjusted_allocations[wallet_address]

                elif override_type == "allocation_override":
                    if wallet_address in adjusted_allocations:
                        adjusted_allocations[wallet_address] = override_value

        return adjusted_allocations

    def _generate_portfolio_summary(
        self,
        allocations: Dict[str, float],
        qualified_wallets: List[Dict[str, Any]],
        criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate comprehensive portfolio summary."""

        # Calculate portfolio metrics
        total_allocated = sum(allocations.values())
        wallet_count = len(allocations)

        # Create wallet allocation details
        wallet_allocations = []
        for wallet in qualified_wallets:
            wallet_address = wallet["address"]
            if wallet_address in allocations:
                wallet_allocations.append({
                    "address": wallet_address,
                    "type": wallet["wallet_info"].get("classification", "unknown"),
                    "quality_score": wallet["quality_score"],
                    "allocated_capital": allocations[wallet_address],
                    "allocation_percentage": (allocations[wallet_address] / total_allocated) * 100,
                    "confidence": wallet["confidence"],
                    "stability_score": wallet["stability_score"],
                    "alerts": wallet["alerts"]
                })

        # Sort by allocation size
        wallet_allocations.sort(key=lambda x: x["allocated_capital"], reverse=True)

        # Calculate portfolio quality metrics
        avg_quality_score = np.mean([w["quality_score"] for w in wallet_allocations])
        avg_stability = np.mean([w["stability_score"] for w in wallet_allocations])
        quality_diversity = np.std([w["quality_score"] for w in wallet_allocations])

        # Portfolio risk assessment
        risk_assessment = self._assess_portfolio_risk(wallet_allocations, allocations)

        return {
            "portfolio_overview": {
                "total_allocated_capital": total_allocated,
                "wallet_count": wallet_count,
                "average_quality_score": avg_quality_score,
                "average_stability_score": avg_stability,
                "quality_score_diversity": quality_diversity,
                "selection_criteria": criteria
            },
            "wallet_allocations": wallet_allocations,
            "portfolio_risk_assessment": risk_assessment,
            "selection_timestamp": datetime.now().isoformat(),
            "manual_overrides_applied": bool(self.manual_overrides)
        }

    def _assess_portfolio_risk(
        self,
        wallet_allocations: List[Dict[str, Any]],
        allocations: Dict[str, float]
    ) -> Dict[str, Any]:
        """Assess overall portfolio risk."""

        try:
            # Concentration risk
            total_capital = sum(allocations.values())
            allocations_pct = [(alloc / total_capital) for alloc in allocations.values()]
            hhi_index = sum(pct ** 2 for pct in allocations_pct)  # Herfindahl-Hirschman Index

            # Quality risk
            quality_scores = [w["quality_score"] for w in wallet_allocations]
            quality_volatility = np.std(quality_scores)

            # Stability risk
            stability_scores = [w["stability_score"] for w in wallet_allocations]
            stability_volatility = np.std(stability_scores)

            # Alert risk
            total_alerts = sum(len(w["alerts"]) for w in wallet_allocations)
            alert_risk = total_alerts / len(wallet_allocations) if wallet_allocations else 0

            # Overall risk score (0-100, higher = riskier)
            concentration_risk = min(100, hhi_index * 1000)  # Scale HHI to 0-100
            quality_risk = max(0, 100 - np.mean(quality_scores))  # Lower quality = higher risk
            stability_risk = (1 - np.mean(stability_scores)) * 100  # Lower stability = higher risk
            alert_risk_score = alert_risk * 50  # Scale alerts to 0-100

            overall_risk = (
                concentration_risk * 0.3 +
                quality_risk * 0.3 +
                stability_risk * 0.2 +
                alert_risk_score * 0.2
            )

            # Risk rating
            if overall_risk < 25:
                risk_rating = "very_low"
            elif overall_risk < 40:
                risk_rating = "low"
            elif overall_risk < 60:
                risk_rating = "moderate"
            elif overall_risk < 80:
                risk_rating = "high"
            else:
                risk_rating = "very_high"

            return {
                "overall_risk_score": overall_risk,
                "risk_rating": risk_rating,
                "concentration_risk": concentration_risk,
                "quality_risk": quality_risk,
                "stability_risk": stability_risk,
                "alert_risk": alert_risk_score,
                "hhi_concentration_index": hhi_index,
                "risk_factors": self._identify_risk_factors(wallet_allocations)
            }

        except Exception as e:
            logger.error(f"Error assessing portfolio risk: {e}")
            return {"overall_risk_score": 50, "risk_rating": "unknown", "error": str(e)}

    def _identify_risk_factors(self, wallet_allocations: List[Dict[str, Any]]) -> List[str]:
        """Identify key risk factors in the portfolio."""

        risk_factors = []

        # Check for concentration
        total_capital = sum(w["allocated_capital"] for w in wallet_allocations)
        large_positions = [
            w for w in wallet_allocations
            if (w["allocated_capital"] / total_capital) > 0.2  # >20% allocation
        ]
        if large_positions:
            risk_factors.append(f"High concentration in {len(large_positions)} wallet(s)")

        # Check for low quality wallets
        low_quality = [w for w in wallet_allocations if w["quality_score"] < 60]
        if low_quality:
            risk_factors.append(f"{len(low_quality)} wallet(s) with quality score < 60")

        # Check for unstable wallets
        unstable = [w for w in wallet_allocations if w["stability_score"] < 0.6]
        if unstable:
            risk_factors.append(f"{len(unstable)} wallet(s) with low stability")

        # Check for wallets with alerts
        with_alerts = [w for w in wallet_allocations if w["alerts"]]
        if with_alerts:
            risk_factors.append(f"{len(with_alerts)} wallet(s) have active alerts")

        return risk_factors

    def _store_portfolio_state(self, allocations: Dict[str, float], criteria: Dict[str, Any]):
        """Store current portfolio state."""

        portfolio_state = {
            "timestamp": datetime.now().isoformat(),
            "allocations": allocations,
            "criteria": criteria,
            "total_capital": sum(allocations.values()),
            "wallet_count": len(allocations)
        }

        self.portfolio_history.append(portfolio_state)

        # Keep only recent history
        max_history = 100
        if len(self.portfolio_history) > max_history:
            self.portfolio_history = self.portfolio_history[-max_history:]

    async def check_portfolio_rotation(self, current_portfolio: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Check if portfolio rotation is needed based on performance and score changes.

        Args:
            current_portfolio: Current portfolio allocations

        Returns:
            Rotation decision with rationale
        """

        rotation_decision = {
            "rotation_needed": False,
            "rotation_type": None,
            "wallets_to_remove": [],
            "wallets_to_add": [],
            "rotation_rationale": [],
            "expected_impact": {},
            "check_timestamp": datetime.now().isoformat()
        }

        try:
            # Check rotation cooldown
            if self._is_rotation_cooldown_active():
                rotation_decision["rationale"] = ["Rotation cooldown period active"]
                return rotation_decision

            # Check for underperforming wallets
            underperformers = await self._identify_underperforming_wallets(current_portfolio)

            # Check for new high-quality wallets
            new_candidates = await self._identify_new_wallet_candidates(current_portfolio)

            # Evaluate rotation benefits
            rotation_benefits = self._evaluate_rotation_benefits(
                underperformers, new_candidates, current_portfolio
            )

            # Make rotation decision
            if rotation_benefits["net_benefit"] > self.selection_params["rotation_threshold"]:
                rotation_decision["rotation_needed"] = True
                rotation_decision["rotation_type"] = rotation_benefits["recommended_type"]
                rotation_decision["wallets_to_remove"] = [w["address"] for w in underperformers[:rotation_benefits["removal_count"]]]
                rotation_decision["wallets_to_add"] = [w["address"] for w in new_candidates[:rotation_benefits["addition_count"]]]
                rotation_decision["rotation_rationale"] = rotation_benefits["rationale"]
                rotation_decision["expected_impact"] = rotation_benefits["expected_impact"]

                # Log rotation
                self._log_portfolio_rotation(rotation_decision)

            return rotation_decision

        except Exception as e:
            logger.error(f"Error checking portfolio rotation: {e}")
            rotation_decision["error"] = str(e)
            return rotation_decision

    def _is_rotation_cooldown_active(self) -> bool:
        """Check if rotation cooldown period is active."""

        if not self.rotation_history:
            return False

        last_rotation = self.rotation_history[-1]
        last_rotation_time = datetime.fromisoformat(last_rotation["timestamp"])
        cooldown_period = timedelta(days=self.selection_params["rotation_cooldown_days"])

        return datetime.now() - last_rotation_time < cooldown_period

    async def _identify_underperforming_wallets(self, current_portfolio: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify wallets that are underperforming in the current portfolio."""

        underperformers = []

        for wallet_address, wallet_data in current_portfolio.items():
            # Get current score
            current_score_data = await self.real_time_scorer.get_real_time_score(wallet_address)

            if "current_score" in current_score_data:
                current_score = current_score_data["current_score"]
                initial_score = wallet_data.get("initial_quality_score", current_score)

                # Calculate performance relative to initial score
                score_change = (current_score - initial_score) / max(abs(initial_score), 0.1)

                # Check for significant deterioration
                if score_change < -self.selection_params["rotation_threshold"]:
                    underperformers.append({
                        "address": wallet_address,
                        "current_score": current_score,
                        "initial_score": initial_score,
                        "score_change": score_change,
                        "reason": "significant_score_decline"
                    })

            # Check for stability issues
            stability = current_score_data.get("stability_metrics", {})
            if stability.get("stability_score", 1.0) < 0.5:
                if not any(u["address"] == wallet_address for u in underperformers):
                    underperformers.append({
                        "address": wallet_address,
                        "current_score": current_score_data.get("current_score", 0),
                        "reason": "low_stability"
                    })

        # Sort by severity
        underperformers.sort(key=lambda x: x.get("score_change", 0))

        return underperformers

    async def _identify_new_wallet_candidates(self, current_portfolio: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify high-quality wallets not currently in the portfolio."""

        # This would query available wallets and score them
        # Simplified implementation
        candidates = []

        # Placeholder: in practice would scan all available wallets
        # and return those with scores significantly higher than current portfolio average

        return candidates

    def _evaluate_rotation_benefits(
        self,
        underperformers: List[Dict[str, Any]],
        new_candidates: List[Dict[str, Any]],
        current_portfolio: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Evaluate the benefits of portfolio rotation."""

        benefits_analysis = {
            "net_benefit": 0.0,
            "recommended_type": None,
            "removal_count": 0,
            "addition_count": 0,
            "rationale": [],
            "expected_impact": {}
        }

        try:
            # Calculate current portfolio score
            current_scores = [w.get("current_score", 0) for w in current_portfolio.values()]
            current_avg_score = np.mean(current_scores) if current_scores else 0

            # Calculate score improvement potential
            if underperformers and new_candidates:
                # Partial rotation: replace underperformers with new candidates
                removal_scores = [u.get("current_score", 0) for u in underperformers]
                addition_scores = [c.get("score", 0) for c in new_candidates]

                # Calculate expected new average score
                remaining_scores = [s for s in current_scores if s not in removal_scores]
                new_portfolio_scores = remaining_scores + addition_scores[:len(underperformers)]

                if new_portfolio_scores:
                    new_avg_score = np.mean(new_portfolio_scores)
                    score_improvement = new_avg_score - current_avg_score

                    if score_improvement > self.selection_params["rotation_threshold"]:
                        benefits_analysis["net_benefit"] = score_improvement
                        benefits_analysis["recommended_type"] = "partial_rotation"
                        benefits_analysis["removal_count"] = len(underperformers)
                        benefits_analysis["addition_count"] = min(len(underperformers), len(new_candidates))
                        benefits_analysis["rationale"] = [
                            f"Expected score improvement: +{score_improvement:.1f} points",
                            f"Replacing {len(underperformers)} underperforming wallets"
                        ]
                        benefits_analysis["expected_impact"] = {
                            "score_improvement": score_improvement,
                            "risk_change": "moderate",  # Assumes similar risk profiles
                            "diversification_impact": "neutral"
                        }

        except Exception as e:
            logger.error(f"Error evaluating rotation benefits: {e}")

        return benefits_analysis

    def _log_portfolio_rotation(self, rotation_decision: Dict[str, Any]):
        """Log portfolio rotation event."""

        rotation_record = {
            "timestamp": rotation_decision["check_timestamp"],
            "rotation_type": rotation_decision["rotation_type"],
            "wallets_removed": rotation_decision["wallets_to_remove"],
            "wallets_added": rotation_decision["wallets_to_add"],
            "rationale": rotation_decision["rotation_rationale"],
            "expected_impact": rotation_decision["expected_impact"]
        }

        self.rotation_history.append(rotation_record)

        # Keep only recent history
        max_history = 50
        if len(self.rotation_history) > max_history:
            self.rotation_history = self.rotation_history[-max_history:]

    def apply_manual_override(
        self,
        wallet_address: str,
        override_type: str,
        override_value: Any,
        reason: str,
        override_duration_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Apply manual override to wallet selection logic.

        Args:
            wallet_address: Wallet to override
            override_type: Type of override ("force_include", "force_exclude", "allocation_override")
            override_value: Override value (allocation amount for allocation_override)
            reason: Reason for override
            override_duration_hours: Hours until override expires

        Returns:
            Override application result
        """

        try:
            expiry_time = datetime.now() + timedelta(hours=override_duration_hours)

            override_record = {
                "wallet_address": wallet_address,
                "override_type": override_type,
                "override_value": override_value,
                "reason": reason,
                "applied_at": datetime.now().isoformat(),
                "expiry_time": expiry_time.isoformat(),
                "applied_by": "manual_override"
            }

            self.manual_overrides[wallet_address] = override_record
            self.override_audit_log.append(override_record)

            # Clean expired overrides
            self._clean_expired_overrides()

            return {
                "success": True,
                "override_id": f"{wallet_address}_{override_record['applied_at']}",
                "expiry_time": expiry_time.isoformat(),
                "message": f"Manual override applied to {wallet_address}"
            }

        except Exception as e:
            logger.error(f"Error applying manual override: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _clean_expired_overrides(self):
        """Remove expired manual overrides."""

        current_time = datetime.now()
        expired_wallets = []

        for wallet_address, override_data in self.manual_overrides.items():
            expiry_time = datetime.fromisoformat(override_data["expiry_time"])

            if current_time >= expiry_time:
                expired_wallets.append(wallet_address)

        for wallet_address in expired_wallets:
            del self.manual_overrides[wallet_address]

    def get_portfolio_status(self) -> Dict[str, Any]:
        """Get current portfolio selection status."""

        try:
            current_portfolio = self.portfolio_history[-1] if self.portfolio_history else {}

            return {
                "current_portfolio": current_portfolio,
                "active_manual_overrides": len(self.manual_overrides),
                "last_rotation": self.rotation_history[-1] if self.rotation_history else None,
                "portfolio_count": len(current_portfolio.get("allocations", {})),
                "total_allocated": current_portfolio.get("total_capital", 0),
                "selection_system_health": "healthy" if current_portfolio else "no_portfolio"
            }

        except Exception as e:
            logger.error(f"Error getting portfolio status: {e}")
            return {"error": str(e)}

    def save_selector_state(self):
        """Save wallet selector state."""

        try:
            state_dir = Path("data/wallet_selection")
            state_dir.mkdir(parents=True, exist_ok=True)

            # Save portfolio history
            with open(state_dir / "portfolio_history.json", 'w') as f:
                json.dump(self.portfolio_history, f, indent=2, default=str)

            # Save rotation history
            with open(state_dir / "rotation_history.json", 'w') as f:
                json.dump(self.rotation_history, f, indent=2, default=str)

            # Save manual overrides
            with open(state_dir / "manual_overrides.json", 'w') as f:
                json.dump(self.manual_overrides, f, indent=2, default=str)

            # Save override audit log
            with open(state_dir / "override_audit.json", 'w') as f:
                json.dump(self.override_audit_log[-200:], f, indent=2, default=str)  # Last 200 entries

            logger.info(f"💾 Wallet selector state saved to {state_dir}")

        except Exception as e:
            logger.error(f"Error saving selector state: {e}")

    def load_selector_state(self):
        """Load wallet selector state."""

        try:
            state_dir = Path("data/wallet_selection")

            # Load portfolio history
            portfolio_file = state_dir / "portfolio_history.json"
            if portfolio_file.exists():
                with open(portfolio_file, 'r') as f:
                    self.portfolio_history = json.load(f)

            # Load rotation history
            rotation_file = state_dir / "rotation_history.json"
            if rotation_file.exists():
                with open(rotation_file, 'r') as f:
                    self.rotation_history = json.load(f)

            # Load manual overrides
            overrides_file = state_dir / "manual_overrides.json"
            if overrides_file.exists():
                with open(overrides_file, 'r') as f:
                    self.manual_overrides = json.load(f)

            # Load override audit log
            audit_file = state_dir / "override_audit.json"
            if audit_file.exists():
                with open(audit_file, 'r') as f:
                    self.override_audit_log = json.load(f)

            logger.info(f"📊 Wallet selector state loaded from {state_dir}")

        except Exception as e:
            logger.error(f"Error loading selector state: {e}")

    def _create_insufficient_wallets_response(self, qualified_wallets: List[Dict[str, Any]], criteria: Dict[str, Any]) -> Dict[str, Any]:
        """Create response when insufficient qualified wallets are available."""

        return {
            "error": "insufficient_qualified_wallets",
            "qualified_wallet_count": len(qualified_wallets),
            "required_min_count": criteria["min_wallet_count"],
            "available_wallets": [
                {
                    "address": w["address"],
                    "quality_score": w["quality_score"],
                    "reason": "below_minimum_count"
                }
                for w in qualified_wallets
            ],
            "selection_timestamp": datetime.now().isoformat()
        }
