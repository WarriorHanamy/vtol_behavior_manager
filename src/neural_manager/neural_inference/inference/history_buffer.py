#!/usr/bin/env python3
"""
Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

Observation History Buffer for MLP Policy Actors

This module implements a circular buffer to maintain observation history
for MLP actors that require temporal information through stacked observations.
"""

import numpy as np
from typing import Optional


class ObservationHistoryBuffer:
    """
    Circular buffer for maintaining observation history for MLP actors.

    This buffer stores the last N observations and provides them in a stacked
    format suitable for neural network inference.
    """

    def __init__(self, history_length: int = 5, obs_dim: int = 16, dtype: np.dtype = np.float32, node_logger=None):
        """
        Initialize the observation history buffer.

        Args:
            history_length: Number of observations to maintain in history
            obs_dim: Dimension of each observation vector
            dtype: Data type for observation storage
            node_logger: ROS2 node logger for structured logging
        """
        self.history_length = history_length
        self.obs_dim = obs_dim
        self.dtype = dtype
        self._logger = node_logger

        # Initialize circular buffer with zeros
        self.buffer = np.zeros((history_length, obs_dim), dtype=dtype)
        self.current_idx = 0
        self.is_filled = False
        self.count = 0

        # Log initialization
        log_msg = f"初始化观测历史缓冲区: 长度={history_length}, 维度={obs_dim}"
        if self._logger:
            self._logger.info(log_msg)
        else:
            print(log_msg)

    def reset(self):
        """Reset the buffer to initial state with zeros."""
        self.buffer.fill(0.0)
        self.current_idx = 0
        self.is_filled = False
        self.count = 0

    def add_observation(self, obs: np.ndarray):
        """
        Add a new observation to the buffer.

        Args:
            obs: New observation vector with shape (obs_dim,)
        """
        if obs.shape != (self.obs_dim,):
            raise ValueError(f"Expected observation shape ({self.obs_dim},), got {obs.shape}")

        # Store observation at current position
        self.buffer[self.current_idx] = obs.astype(self.dtype)

        # Update circular buffer indices
        self.current_idx = (self.current_idx + 1) % self.history_length
        self.count += 1

        # Mark as filled if we've wrapped around
        if self.count >= self.history_length:
            self.is_filled = True

    def get_stacked_history(self) -> np.ndarray:
        """
        Get the stacked observation history for neural network input.

        Returns:
            Stacked observations with shape (history_length * obs_dim,)
            ordered from oldest to newest.
        """
        if not self.is_filled and self.count == 0:
            # No observations yet, return all zeros
            return self.buffer.flatten()

        # Reorder buffer to get chronological order (oldest to newest)
        if self.is_filled:
            # Buffer is full, start from current_idx (which is the oldest)
            ordered = np.zeros_like(self.buffer)
            for i in range(self.history_length):
                src_idx = (self.current_idx + i) % self.history_length
                ordered[i] = self.buffer[src_idx]
        else:
            # Buffer not full, start from index 0
            ordered = self.buffer[:self.count]
            # Pad remaining slots with zeros
            if self.count < self.history_length:
                zeros = np.zeros((self.history_length - self.count, self.obs_dim), dtype=self.dtype)
                ordered = np.vstack([zeros, ordered])
        ordered = ordered[::-1]  # Reverse to have oldest first
        return ordered.flatten()

    def get_last_observation(self) -> Optional[np.ndarray]:
        """
        Get the most recent observation.

        Returns:
            Most recent observation or None if no observations added.
        """
        if self.count == 0:
            return None

        # Get the index of the most recent observation
        last_idx = (self.current_idx - 1) % self.history_length
        return self.buffer[last_idx].copy()

    def get_history_matrix(self) -> np.ndarray:
        """
        Get the history as a 2D matrix.

        Returns:
            History matrix with shape (history_length, obs_dim)
            ordered from oldest to newest, with zeros for unused slots.
        """
        if not self.is_filled and self.count == 0:
            return self.buffer.copy()

        # Reorder buffer to get chronological order
        if self.is_filled:
            ordered = np.zeros_like(self.buffer)
            for i in range(self.history_length):
                src_idx = (self.current_idx + i) % self.history_length
                ordered[i] = self.buffer[src_idx]
        else:
            # Buffer not full, start from index 0
            ordered = np.zeros_like(self.buffer)
            ordered[-self.count:] = self.buffer[:self.count]

        return ordered

    def __len__(self) -> int:
        """Return the number of observations currently stored."""
        return min(self.count, self.history_length)

    def is_ready(self) -> bool:
        """
        Check if the buffer has enough observations for inference.

        Returns:
            True if buffer has at least one observation.
        """
        return self.count > 0

    def get_info(self) -> dict:
        """
        Get buffer information for debugging.

        Returns:
            Dictionary with buffer statistics.
        """
        return {
            "history_length": self.history_length,
            "obs_dim": self.obs_dim,
            "current_count": len(self),
            "is_filled": self.is_filled,
            "current_idx": self.current_idx,
            "total_added": self.count
        }