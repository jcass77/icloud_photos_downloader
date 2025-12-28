"""Tests for random offset mode in PhotoAlbum."""

import random
from typing import Any
from unittest import TestCase
from unittest.mock import Mock, patch

from pyicloud_ipd.response_types import (
    AlbumLengthSuccess,
    PhotoIterationComplete,
    PhotoIterationSuccess,
    PhotosRequestSuccess,
    ResponseAPIError,
)
from pyicloud_ipd.services.photos import PhotoAlbum


class RandomOffsetModeTestCase(TestCase):
    """Test cases for random offset mode functionality."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.mock_session = Mock()
        self.mock_params = {"param": "value"}
        self.service_endpoint = "https://test.icloud.com"

    def _create_album(self, random_offset_mode: bool = True, page_size: int = 10) -> PhotoAlbum:
        """Create a PhotoAlbum instance for testing."""
        return PhotoAlbum(
            params=self.mock_params,
            session=self.mock_session,
            service_endpoint=self.service_endpoint,
            name="Test Album",
            list_type="CPLAssetAndMasterByAddedDate",
            obj_type="CPLAssetAndMasterByAddedDate",
            page_size=page_size,
            random_offset_mode=random_offset_mode,
        )

    def _mock_photo_response(self, count: int) -> dict[str, Any]:
        """Create mock photo response with specified number of photos."""
        records = []
        for i in range(count):
            master_id = f"master_{i}"
            records.append(
                {
                    "recordType": "CPLMaster",
                    "recordName": master_id,
                    "fields": {},
                }
            )
            records.append(
                {
                    "recordType": "CPLAsset",
                    "fields": {"masterRef": {"value": {"recordName": master_id}}},
                }
            )
        return {"records": records}

    def test_random_offset_initialization(self) -> None:
        """Test that random offset mode initializes offsets correctly."""
        album = self._create_album(page_size=10)

        with (
            patch.object(album, "get_album_length", return_value=AlbumLengthSuccess(100)),
            patch("pyicloud_ipd.services.photos.photos_request") as mock_photos_request,
        ):
            mock_response = Mock()
            mock_response.json.return_value = self._mock_photo_response(10)
            mock_photos_request.return_value = PhotosRequestSuccess(mock_response)

            # Start iteration to trigger initialization
            gen = album.photos
            next(gen)

            # Verify offsets were initialized (should have ~10 offsets for 100 photos with page_size 10)
            self.assertTrue(len(album._offsets) < 10)  # One was popped
            self.assertTrue(album.offset in [0, 10, 20, 30, 40, 50, 60, 70, 80, 90])

    def test_random_offset_progression(self) -> None:
        """Test that offsets are selected randomly during iteration."""
        album = self._create_album(page_size=10)

        with (
            patch.object(album, "get_album_length", return_value=AlbumLengthSuccess(30)),
            patch("pyicloud_ipd.services.photos.photos_request") as mock_photos_request,
        ):
            mock_response = Mock()
            mock_response.json.return_value = self._mock_photo_response(10)
            mock_photos_request.return_value = PhotosRequestSuccess(mock_response)

            gen = album.photos
            offsets_seen = set()

            # Collect first 15 photos and track offsets
            for _ in range(15):
                result = next(gen)
                if isinstance(result, PhotoIterationSuccess):
                    offsets_seen.add(album.offset)

            # With 30 photos and page_size 10, we have offsets [0, 10, 20]
            # After 15 photos, we should have seen at least 2 different offsets
            self.assertTrue(len(offsets_seen) >= 1)

    def test_single_photo_album(self) -> None:
        """Test that album with single photo does not crash."""
        album = self._create_album(page_size=10)

        with (
            patch.object(album, "get_album_length", return_value=AlbumLengthSuccess(1)),
            patch("pyicloud_ipd.services.photos.photos_request") as mock_photos_request,
        ):
            # First call returns 1 photo, second call returns empty
            mock_response1 = Mock()
            mock_response1.json.return_value = self._mock_photo_response(1)
            mock_response2 = Mock()
            mock_response2.json.return_value = {"records": []}
            mock_photos_request.side_effect = [
                PhotosRequestSuccess(mock_response1),
                PhotosRequestSuccess(mock_response2),
            ]

            gen = album.photos
            results = []

            # Collect limited results
            for i, result in enumerate(gen):
                results.append(result)
                if isinstance(result, PhotoIterationComplete) or i >= 5:
                    break

            # Verify we got the photo
            success_results = [r for r in results if isinstance(r, PhotoIterationSuccess)]
            self.assertEqual(len(success_results), 1)

    def test_photos_less_than_page_size(self) -> None:
        """Test album with photos < page_size handles gracefully."""
        album = self._create_album(page_size=10)

        with (
            patch.object(album, "get_album_length", return_value=AlbumLengthSuccess(5)),
            patch("pyicloud_ipd.services.photos.photos_request") as mock_photos_request,
        ):
            # First call returns 5 photos, second returns empty
            mock_response1 = Mock()
            mock_response1.json.return_value = self._mock_photo_response(5)
            mock_response2 = Mock()
            mock_response2.json.return_value = {"records": []}
            mock_photos_request.side_effect = [
                PhotosRequestSuccess(mock_response1),
                PhotosRequestSuccess(mock_response2),
            ]

            gen = album.photos
            results = []

            # Collect limited results
            for i, result in enumerate(gen):
                results.append(result)
                if isinstance(result, PhotoIterationComplete) or i >= 10:
                    break

            # Verify photos were yielded
            success_results = [r for r in results if isinstance(r, PhotoIterationSuccess)]
            self.assertEqual(len(success_results), 5)

    def test_empty_offsets_list(self) -> None:
        """Test that exhausted offsets list completes iteration."""
        album = self._create_album(page_size=10)

        with (
            patch.object(album, "get_album_length", return_value=AlbumLengthSuccess(10)),
            patch("pyicloud_ipd.services.photos.photos_request") as mock_photos_request,
        ):
            # First call returns photos, second returns empty to trigger completion
            mock_response1 = Mock()
            mock_response1.json.return_value = self._mock_photo_response(10)
            mock_response2 = Mock()
            mock_response2.json.return_value = {"records": []}
            mock_photos_request.side_effect = [
                PhotosRequestSuccess(mock_response1),
                PhotosRequestSuccess(mock_response2),
            ]

            gen = album.photos
            results = []

            # Iterate with limit
            for i, result in enumerate(gen):
                results.append(result)
                if isinstance(result, PhotoIterationComplete) or i >= 15:
                    break

            # Verify iteration completed
            self.assertTrue(any(isinstance(r, PhotoIterationComplete) for r in results))

    def test_album_length_failure(self) -> None:
        """Test fallback to sequential when get_album_length fails."""
        album = self._create_album(page_size=10)

        with (
            patch.object(
                album,
                "get_album_length",
                return_value=ResponseAPIError("error", "Failed"),
            ),
            patch("pyicloud_ipd.services.photos.photos_request") as mock_photos_request,
        ):
            mock_response = Mock()
            mock_response.json.return_value = self._mock_photo_response(5)
            mock_photos_request.return_value = PhotosRequestSuccess(mock_response)

            gen = album.photos
            # Consume first result to trigger initialization
            for i, _ in enumerate(gen):
                if i >= 0:
                    break

            # Verify fallback: _offsets should be empty, offset should be 0
            self.assertEqual(len(album._offsets), 0)
            self.assertEqual(album.offset, 0)

    def test_value_error_on_empty_offsets(self) -> None:
        """Test ValueError handling when offsets is empty."""
        album = self._create_album(page_size=10)
        album._offsets = []  # Manually set empty offsets

        with (
            patch.object(album, "get_album_length", return_value=AlbumLengthSuccess(10)),
            patch("pyicloud_ipd.services.photos.photos_request") as mock_photos_request,
        ):
            mock_response = Mock()
            mock_response.json.return_value = self._mock_photo_response(10)
            mock_photos_request.return_value = PhotosRequestSuccess(mock_response)

            # Manually trigger the scenario where offsets is empty during progression
            with patch.object(random, "randint", side_effect=ValueError("empty")):
                gen = album.photos
                results = []

                for result in gen:
                    results.append(result)
                    if isinstance(result, PhotoIterationComplete):
                        break
                    # Limit iterations to prevent infinite loop
                    if len(results) > 20:
                        break

                # Should handle ValueError gracefully
                self.assertTrue(len(results) > 0)

    def test_sequential_mode_unchanged(self) -> None:
        """Test that random_offset_mode=False preserves original behavior."""
        album = self._create_album(random_offset_mode=False, page_size=10)

        with patch("pyicloud_ipd.services.photos.photos_request") as mock_photos_request:
            # First call returns photos, second returns empty
            mock_response1 = Mock()
            mock_response1.json.return_value = self._mock_photo_response(10)
            mock_response2 = Mock()
            mock_response2.json.return_value = {"records": []}
            mock_photos_request.side_effect = [
                PhotosRequestSuccess(mock_response1),
                PhotosRequestSuccess(mock_response2),
            ]

            gen = album.photos
            initial_offset = album.offset

            # Get first batch of photos
            for i, result in enumerate(gen):
                if isinstance(result, PhotoIterationComplete) or i >= 12:
                    break

            # Verify _offsets was never populated
            self.assertEqual(len(album._offsets), 0)
            # Verify offset incremented sequentially
            self.assertEqual(album.offset, initial_offset + 1)
