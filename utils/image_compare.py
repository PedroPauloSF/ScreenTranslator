"""
Image comparison utilities.

Provides SSIM (Structural Similarity Index) and perceptual hashing
to detect meaningful changes between successive screen captures.

Both methods are used in tandem: first a fast perceptual hash,
then SSIM for confirmation when the hash indicates a possible change.
"""

from __future__ import annotations

import cv2
import numpy as np
from dataclasses import dataclass


@dataclass
class ImageComparator:
    """Compares two images and determines if they differ meaningfully.

    Attributes:
        ssim_threshold: Minimum SSIM index to consider images identical (0.0 to 1.0).
        hash_threshold: Maximum Hamming distance to consider hashes identical.
    """

    ssim_threshold: float = 0.95
    hash_threshold: int = 5

    def has_changed(self, img_a: np.ndarray, img_b: np.ndarray) -> bool:
        """Check whether img_b differs significantly from img_a.

        Uses SSIM as primary metric. Perceptual hash acts as a fast negative
        filter: if hashes are identical (hamming=0), skip SSIM entirely.
        For any hash difference, SSIM is computed for accurate comparison.

        Args:
            img_a: Previous frame as a BGR numpy array.
            img_b: Current frame as a BGR numpy array.

        Returns:
            True if a meaningful visual change is detected.
        """
        hash_a = compute_perceptual_hash(img_a)
        hash_b = compute_perceptual_hash(img_b)
        hamming = _hamming_distance(hash_a, hash_b)

        if hamming == 0:
            return False

        ssim = compute_ssim(img_a, img_b)
        return ssim < self.ssim_threshold


def compute_ssim(img_a: np.ndarray, img_b: np.ndarray) -> float:
    """Compute the Structural Similarity Index between two images.

    Converts both images to grayscale before comparison.

    Args:
        img_a: First image (BGR).
        img_b: Second image (BGR).

    Returns:
        SSIM value between 0.0 (completely different) and 1.0 (identical).
    """
    gray_a = cv2.cvtColor(img_a, cv2.COLOR_BGR2GRAY)
    gray_b = cv2.cvtColor(img_b, cv2.COLOR_BGR2GRAY)

    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2

    gray_a = gray_a.astype(np.float64)
    gray_b = gray_b.astype(np.float64)

    mu_a = cv2.GaussianBlur(gray_a, (11, 11), 1.5)
    mu_b = cv2.GaussianBlur(gray_b, (11, 11), 1.5)

    mu_a_sq = mu_a ** 2
    mu_b_sq = mu_b ** 2
    mu_ab = mu_a * mu_b

    sigma_a_sq = cv2.GaussianBlur(gray_a ** 2, (11, 11), 1.5) - mu_a_sq
    sigma_b_sq = cv2.GaussianBlur(gray_b ** 2, (11, 11), 1.5) - mu_b_sq
    sigma_ab = cv2.GaussianBlur(gray_a * gray_b, (11, 11), 1.5) - mu_ab

    numerator = (2 * mu_ab + c1) * (2 * sigma_ab + c2)
    denominator = (mu_a_sq + mu_b_sq + c1) * (sigma_a_sq + sigma_b_sq + c2)

    ssim_map = numerator / denominator
    return float(np.mean(ssim_map))


def compute_perceptual_hash(img: np.ndarray, hash_size: int = 8) -> str:
    """Compute a perceptual hash (pHash) for the image.

    Uses DCT-based hashing: resize, convert to grayscale, apply DCT,
    and compare each pixel to the mean of the low-frequency coefficients.

    Args:
        img: Input image (BGR).
        hash_size: Size of the hash square (default 8 yields 64-bit hash).

    Returns:
        Hexadecimal string representation of the hash.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (hash_size * 4, hash_size * 4), interpolation=cv2.INTER_AREA)

    dct = cv2.dct(np.float32(resized))
    dct_low = dct[:hash_size, :hash_size]

    mean = dct_low.mean()
    diff = dct_low > mean

    hash_bytes = np.packbits(diff.flatten())
    return hash_bytes.tobytes().hex()


def _hamming_distance(hash_a: str, hash_b: str) -> int:
    """Compute the Hamming distance between two hex-encoded hashes.

    Args:
        hash_a: First hash as a hex string.
        hash_b: Second hash as a hex string.

    Returns:
        Number of differing bits.
    """
    if len(hash_a) != len(hash_b):
        return max(len(hash_a), len(hash_b)) * 4

    bytes_a = bytes.fromhex(hash_a)
    bytes_b = bytes.fromhex(hash_b)

    distance = 0
    for ba, bb in zip(bytes_a, bytes_b):
        distance += (ba ^ bb).bit_count()
    return distance
