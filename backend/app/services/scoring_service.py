"""Multi-factor explainable engagement scoring service for candidate clips."""

import math
from typing import Dict, Any, Optional, List
from backend.app.models.candidate import ScoreBreakdown
from backend.app.models.audio import ReactionCategory, ClipAudioProfile


class ScoringService:
    """Evaluates candidates using explainable short-form multimodal engagement criteria."""

    def compute_candidate_score(self, candidate_data: Dict[str, Any]) -> ScoreBreakdown:
        """
        Calculates candidate score. Routes to multimodal engine while maintaining
        compatibility with legacy parameter names.
        """
        return self.compute_multimodal_candidate_score(candidate_data)

    def compute_multimodal_candidate_score(
        self,
        candidate_data: Dict[str, Any],
        audio_profile: Optional[ClipAudioProfile] = None,
        visual_profile: Optional[Dict[str, Any]] = None,
    ) -> ScoreBreakdown:
        """
        Calculates a calibrated, non-saturating 0-100 engagement score fusing:
        - Transcript / Context Score (25%)
        - Hook Grab Strength (20%)
        - Audio Reaction Score (20%)
        - Streamer Visual Reaction Score (15%)
        - Gameplay Activity Score (10%)
        - Payoff / Resolution Score (10%)
        Minus explicit penalties:
        - Missing Setup (-15)
        - Dead Air / Long Pause (-10)
        - Abrupt Cutoff before Payoff (-15)
        - Loud non-speech noise (-10)
        Calibrated with non-linear hyperbolic tangent above 80:
        Score = 80 + 15 * tanh((raw - 80) / 15)
        """
        # 1. Transcript / Context Score (0-100)
        transcript_context = float(candidate_data.get("transcript_context_score", 0.0))
        if transcript_context <= 0.0:
            density = float(candidate_data.get("density_score", 18.0))
            clarity = float(candidate_data.get("clarity_score", 18.0))
            transcript_context = (density + clarity) * 2.0
        transcript_context = max(0.0, min(100.0, transcript_context))

        # 2. Hook Grab Score (0-100)
        hook = float(candidate_data.get("hook_score", 0.0))
        if hook <= 0.0 or ("clarity_score" in candidate_data and hook <= 25.0):
            if "hook_strength" in candidate_data:
                hook = float(candidate_data.get("hook_strength", 20.0)) * 4.0
            elif "hook_score" in candidate_data and hook <= 25.0:
                hook = hook * 4.0
            else:
                hook = 80.0
        hook = max(0.0, min(100.0, hook))

        # 3. Audio Reaction Score (0-100)
        if audio_profile is not None:
            audio_reaction = audio_profile.audio_reaction_score
            peak_z = audio_profile.peak_z_score
            has_speech_surge = getattr(audio_profile, "has_speech_corroboration", getattr(audio_profile, "is_speech_corroborated", True))
            reaction_density = audio_profile.reaction_density
        else:
            if "audio_reaction_score" in candidate_data:
                audio_reaction = float(candidate_data["audio_reaction_score"])
            else:
                # Default audio reaction aligns with transcript context in legacy mode
                audio_reaction = max(50.0, transcript_context * 0.9)
            peak_z = float(candidate_data.get("peak_z_score", 0.0))
            has_speech_surge = bool(candidate_data.get("has_speech_corroboration", candidate_data.get("is_speech_corroborated", True)))
            reaction_density = float(candidate_data.get("reaction_density", 0.0))
        audio_reaction = max(0.0, min(100.0, audio_reaction))

        # 4. Streamer Visual Reaction Score (0-100)
        if visual_profile is not None:
            streamer_visual = float(visual_profile.get("streamer_visual_reaction_score", 50.0))
        else:
            if "streamer_visual_reaction_score" in candidate_data:
                streamer_visual = float(candidate_data["streamer_visual_reaction_score"])
            else:
                streamer_visual = max(50.0, transcript_context * 0.85)
        streamer_visual = max(0.0, min(100.0, streamer_visual))

        # 5. Gameplay Activity Score (0-100)
        if visual_profile is not None:
            gameplay_activity = float(visual_profile.get("gameplay_activity_score", 50.0))
        else:
            if "gameplay_activity_score" in candidate_data:
                gameplay_activity = float(candidate_data["gameplay_activity_score"])
            else:
                gameplay_activity = max(50.0, transcript_context * 0.85)
        gameplay_activity = max(0.0, min(100.0, gameplay_activity))

        # 6. Payoff Score (0-100)
        payoff = float(candidate_data.get("payoff_score", 0.0))
        if payoff <= 0.0:
            payoff = float(candidate_data.get("pacing_score", 20.0)) * 4.0
        payoff = max(0.0, min(100.0, payoff))

        # Compute balanced weighted base score
        weighted_base = (
            0.25 * transcript_context +
            0.20 * hook +
            0.20 * audio_reaction +
            0.15 * streamer_visual +
            0.10 * gameplay_activity +
            0.10 * payoff
        )

        # 7. Explicit Penalties
        penalties = 0.0
        penalty_reasons: List[str] = []

        peak_time = candidate_data.get("peak_time")
        start_time = float(candidate_data.get("start_time", 0.0))
        end_time = float(candidate_data.get("end_time", 30.0))
        duration = float(candidate_data.get("duration", end_time - start_time))

        if peak_time is not None:
            if (peak_time - start_time) < 3.0:
                penalties += 15.0
                penalty_reasons.append("missing setup (-15)")
            if (end_time - peak_time) < 3.0:
                penalties += 15.0
                penalty_reasons.append("abrupt cutoff before payoff (-15)")
        else:
            if candidate_data.get("missing_setup", False):
                penalties += 15.0
                penalty_reasons.append("missing setup (-15)")
            if candidate_data.get("abrupt_cutoff", False):
                penalties += 15.0
                penalty_reasons.append("abrupt cutoff (-15)")

        if candidate_data.get("has_dead_air", False):
            penalties += 10.0
            penalty_reasons.append("dead air / awkward silence (-10)")

        if not has_speech_surge and peak_z >= 2.0:
            penalties += 10.0
            penalty_reasons.append("unverified non-speech loud noise (-10)")

        if duration < 18.0 or duration > 55.0:
            penalties += 5.0
            penalty_reasons.append("sub-optimal duration (-5)")

        raw_score = max(0.0, weighted_base - penalties)

        # 8. Anti-saturation non-linear calibration (tanh compression above 80)
        if raw_score > 80.0:
            calibrated = 80.0 + 15.0 * math.tanh((raw_score - 80.0) / 15.0)
        else:
            calibrated = raw_score

        total = int(round(max(0.0, min(100.0, calibrated))))

        # 9. Classify reaction category
        category = self._classify_reaction_category(candidate_data, audio_profile)

        # 10. Generate multimodal explainable summary
        explanation = self._generate_multimodal_explanation(
            category=category,
            total=total,
            transcript_score=transcript_context,
            audio_score=audio_reaction,
            streamer_score=streamer_visual,
            gameplay_score=gameplay_activity,
            hook_score=hook,
            payoff_score=payoff,
            peak_z=peak_z,
            penalties=penalties,
            penalty_reasons=penalty_reasons
        )

        return ScoreBreakdown(
            hook_strength=round(hook / 4.0, 1),
            standalone_clarity=round(transcript_context / 4.0, 1),
            information_density=round(gameplay_activity / 4.0, 1),
            pacing_and_flow=round(payoff / 4.0, 1),
            category=category,
            transcript_context_score=round(transcript_context, 1),
            audio_reaction_score=round(audio_reaction, 1),
            streamer_visual_reaction_score=round(streamer_visual, 1),
            gameplay_activity_score=round(gameplay_activity, 1),
            hook_score=round(hook, 1),
            payoff_score=round(payoff, 1),
            penalties=round(penalties, 1),
            peak_z_score=round(peak_z, 2),
            reaction_density=round(reaction_density, 2),
            total_score=total,
            explanation=explanation
        )

    def _classify_reaction_category(
        self,
        candidate_data: Dict[str, Any],
        audio_profile: Optional[ClipAudioProfile]
    ) -> ReactionCategory:
        """Determines the reaction category from candidate metadata and semantic text."""
        raw_cat = candidate_data.get("category")
        if isinstance(raw_cat, ReactionCategory):
            return raw_cat
        if isinstance(raw_cat, str):
            try:
                return ReactionCategory(raw_cat)
            except ValueError:
                pass

        text_corpus = " ".join([
            str(candidate_data.get("title", "")),
            str(candidate_data.get("reasoning", "")),
            str(candidate_data.get("transcript_excerpt", ""))
        ]).lower()

        if any(w in text_corpus for w in ["rage", "scream", "angry", "shout", "mad"]):
            return ReactionCategory.RAGE
        if any(w in text_corpus for w in ["fail", "wasted", "died", "crashed", "busted"]):
            return ReactionCategory.FAIL
        if any(w in text_corpus for w in ["laugh", "funny", "haha", "joke", "lol", "hilarious"]):
            return ReactionCategory.FUNNY_REACTION
        if any(w in text_corpus for w in ["surprise", "shock", "what?!", "no way", "unbelievable"]):
            return ReactionCategory.SURPRISE
        if any(w in text_corpus for w in ["chaos", "chaotic", "insane", "explosion"]):
            return ReactionCategory.CHAOTIC_MOMENT
        if any(w in text_corpus for w in ["win", "victory", "clutch"]):
            return ReactionCategory.WIN
        if any(w in text_corpus for w in ["dialogue", "banter", "talking"]):
            return ReactionCategory.FUNNY_DIALOGUE
        if any(w in text_corpus for w in ["epic", "legendary", "crazy shot"]):
            return ReactionCategory.EPIC_MOMENT

        return ReactionCategory.GENERAL_HIGHLIGHT

    def _generate_multimodal_explanation(
        self,
        category: ReactionCategory,
        total: int,
        transcript_score: float,
        audio_score: float,
        streamer_score: float,
        gameplay_score: float,
        hook_score: float,
        payoff_score: float,
        peak_z: float,
        penalties: float,
        penalty_reasons: List[str]
    ) -> str:
        """Constructs an explainable summary detailing active multimodal drivers."""
        drivers = []
        if audio_score >= 75.0:
            drivers.append(f"high-energy audio reaction surge (Z={peak_z:.1f})")
        if streamer_score >= 70.0:
            drivers.append("intense streamer facecam motion")
        if gameplay_score >= 70.0:
            drivers.append("dynamic gameplay action")
        if transcript_score >= 75.0:
            drivers.append("strong narrative setup and context")
        if hook_score >= 80.0:
            drivers.append("compelling opening hook")
        if payoff_score >= 75.0:
            drivers.append("clean climactic payoff")

        driver_str = ", ".join(drivers) if drivers else "balanced multimodal signals"
        penalty_str = f" Deductions: {', '.join(penalty_reasons)}." if penalty_reasons else ""

        if total >= 88:
            prefix = f"Outstanding {category.value.replace('_', ' ')} with top viral potential (Total: {total})."
        elif total >= 75:
            prefix = f"Strong {category.value.replace('_', ' ')} candidate with proven retention signals (Total: {total})."
        else:
            prefix = f"Viable {category.value.replace('_', ' ')} candidate suitable as secondary cut (Total: {total})."

        return f"{prefix} Driven by {driver_str}.{penalty_str}"


scoring_service = ScoringService()
