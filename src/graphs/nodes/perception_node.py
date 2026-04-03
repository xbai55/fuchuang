"""
Perception node for the graph workflow.
Replaces the old multimodal_input_node.py with the new perception layer.
"""
from typing import Any, Dict, List

from langchain_core.runnables import RunnableConfig

from src.core.interfaces import BaseNode
from src.core.models import GlobalState, MediaFile, PerceptionResult
from perception import PerceptionManager, ProcessingContext, get_perception_manager


class PerceptionNode(BaseNode):
    """
    Graph node for multi-modal perception processing.

    Input: GlobalState with input_files
    Output: Updated GlobalState with perception_results

    This replaces the 402-line multimodal_input_node.py with a cleaner
    implementation using the new perception layer.
    """

    def __init__(self, perception_manager: PerceptionManager = None):
        super().__init__("perception")
        self.manager = perception_manager or get_perception_manager()

    async def process(
        self,
        state: GlobalState,
        config: RunnableConfig,
    ) -> Dict[str, Any]:
        """
        Process all media inputs.

        Args:
            state: Global state with input_files
            config: Runnable config

        Returns:
            Dict with perception_results
        """
        # Collect all media files to process
        media_files: List[MediaFile] = []

        # Add direct text input as media file if present
        if state.input_text:
            media_files.append(MediaFile(
                type="text",
                url=state.input_text,
            ))

        # Add uploaded files
        media_files.extend(state.input_files)

        if not media_files:
            # No inputs to process
            return {"perception_results": []}

        # Create processing context
        context = ProcessingContext(
            task_id=state.workflow_metadata.get("task_id"),
            user_role=state.user_context.user_role.value,
            guardian_name=state.user_context.guardian_name,
            metadata={
                "prefer_ai_rate_early_warning": bool(
                    state.workflow_metadata.get("prefer_ai_rate_early_warning", False)
                ),
                "image_ai_probability": state.workflow_metadata.get("image_ai_probability"),
                "image_ai_risk_level": state.workflow_metadata.get("image_ai_risk_level"),
                "image_ai_ocr_skip_threshold": state.workflow_metadata.get("image_ai_ocr_skip_threshold"),
            },
        )

        # Process all media
        results = await self.manager.process(media_files, context)

        return {"perception_results": results}

    def _extract_input(self, state: GlobalState) -> GlobalState:
        """Pass through full state."""
        return state

    def _output_to_dict(self, output: Dict[str, Any]) -> Dict[str, Any]:
        """Return as-is."""
        return output

    def _get_fallback_output(self) -> Dict[str, Any]:
        """Return empty results on failure."""
        return {"perception_results": []}

    @staticmethod
    def from_file_paths(
        text: str = None,
        audio_path: str = None,
        image_path: str = None,
        video_path: str = None,
    ) -> List[MediaFile]:
        """
        Helper to create media files from paths.

        Args:
            text: Text content
            audio_path: Audio file path
            image_path: Image file path
            video_path: Video file path

        Returns:
            List of MediaFile objects
        """
        files = []

        if text:
            files.append(MediaFile(type="text", url=text))

        if audio_path:
            files.append(MediaFile(type="audio", url=audio_path))

        if image_path:
            files.append(MediaFile(type="image", url=image_path))

        if video_path:
            files.append(MediaFile(type="video", url=video_path))

        return files
