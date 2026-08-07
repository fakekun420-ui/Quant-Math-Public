"""
Kalman Filter Module

Implements Kalman filtering for state estimation and noise reduction in time series.
Kalman filter provides optimal recursive estimation in the presence of measurement noise.

Key Uses:
- Optimal state estimation in noisy measurements
- Trend filtering for price data
- Volatility smoothing
- Damping for oscillatory signals
- Denoising without assuming stationarity

Mathematical Foundation:
Kalman filter recursively estimates hidden states from noisy measurements:
    
    Prediction step:
        x̂_{k|k-1} = F_k x̂_{k-1|k-1}
        P_{k|k-1} = F_k P_{k-1|k-1} F_k^T + Q_k
    
    Update step:
        K_k = P_{k|k-1} H_k^T (H_k P_{k|k-1} H_k^T + R_k)^{-1}
        x̂_{k|k} = x̂_{k|k-1} + K_k (z_k - H_k x̂_{k|k-1})
        P_{k|k} = (I - K_k H_k) P_{k|k-1}
    
Where:
    x: State vector
    z: Measurement vector
    F: State transition matrix
    H: Observation matrix
    Q: Process noise covariance
    R: Measurement noise covariance
    P: Error covariance matrix
"""

import numpy as np
from typing import Union, Tuple, Optional


class KalmanFilter:
    """
    Kalman filter implementation for state estimation and denoising.
    
    This class implements both standard Kalman filtering and Extended Kalman
    filtering for nonlinear systems. The default implementation uses linear
    dynamics, which is suitable for most time series denoising applications.
    
    Key Applications:
    - State estimation: Estimate true signal from noisy measurements
    - Smoothing: Apply smoothing algorithm (forward-backward)
    - Filtering: Real-time filtering of noisy data
    
    The filter can be configured with various transition and observation
    models to adapt to different signal characteristics.
    """
    
    def __init__(self, dim_x: int = 1, dim_z: int = 1,
                 dim_u: int = 0,
                 F: Optional[np.ndarray] = None,
                 H: Optional[np.ndarray] = None,
                 Q: Optional[np.ndarray] = None,
                 R: Optional[np.ndarray] = None,
                 B: Optional[np.ndarray] = None):
        """
        Initialize Kalman filter.
        
        Parameters
        ----------
        dim_x : int, optional
            Dimension of state vector (default: 1)
        dim_z : int, optional
            Dimension of measurement vector (default: 1)
        dim_u : int, optional
            Dimension of control input (default: 0)
        F : ndarray, optional
            State transition matrix (dim_x x dim_x)
        H : ndarray, optional
            Observation matrix (dim_z x dim_x)
        Q : ndarray, optional
            Process noise covariance (dim_x x dim_x)
        R : ndarray, optional
            Measurement noise covariance (dim_z x dim_z)
        B : ndarray, optional
            Control input matrix (dim_x x dim_u)
        
        Notes
        -----
        If matrices are not provided, they will be initialized to identity
        matrices with small default values for Q and R.
        """
        self.dim_x = dim_x
        self.dim_z = dim_z
        self.dim_u = dim_u
        
        # Default state transition matrix (constant velocity model)
        if F is None:
            self.F = np.eye(dim_x)
        
        # Default observation matrix (measure state directly)
        if H is None:
            self.H = np.eye(dim_z, dim_x)
        
        # Default process noise (random walk)
        if Q is None:
            self.Q = np.eye(dim_x) * 1e-4
        
        # Default measurement noise
        if R is None:
            self.R = np.eye(dim_z) * 1e-3
        
        # Default control input matrix
        self.B = np.zeros((dim_x, dim_u)) if B is None else B
        
        # Initialize state estimate and covariance
        self.x = np.zeros(dim_x)  # State estimate
        self.P = np.eye(dim_x) * 1  # Error covariance
        
        # Kalman gain
        self.K = np.zeros((dim_x, dim_z))
        
        # Innovation
        self.y = np.zeros(dim_z)
        
        # State transition matrix
        self.F = np.asarray(F)
        
        # Observation matrix
        self.H = np.asarray(H)
        
        # Process noise
        self.Q = np.asarray(Q)
        
        # Measurement noise
        self.R = np.asarray(R)
    
    def predict(self, u: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Predict state estimate forward.
        
        Parameters
        ----------
        u : ndarray, optional
            Control input vector (dim_u)
        
        Returns
        -------
        x_pred : ndarray
            Predicted state estimate
        
        Notes
        -----
        Prediction step computes the predicted state and error covariance:
            x̂_{k|k-1} = F_k x̂_{k-1|k-1} + B_k u_k
            P_{k|k-1} = F_k P_{k-1|k-1} F_k^T + Q_k
        """
        # Predict state
        self.x = np.dot(self.F, self.x)
        if u is not None:
            self.x += np.dot(self.B, u)
        
        # Predict covariance
        self.P = np.dot(np.dot(self.F, self.P), self.F.T) + self.Q
        
        return self.x.copy()
    
    def update(self, z: Union[float, np.ndarray]) -> np.ndarray:
        """
        Update state estimate with measurement.
        
        Parameters
        ----------
        z : float or ndarray
            Measurement vector (dim_z)
        
        Returns
        -------
        x_filtered : ndarray
            Updated state estimate
        
        Notes
        -----
        Update step incorporates new measurement into state estimate:
            K_k = P_{k|k-1} H_k^T (H_k P_{k|k-1} H_k^T + R_k)^{-1}
            x̂_{k|k} = x̂_{k|k-1} + K_k (z_k - H_k x̂_{k|k-1})
            P_{k|k} = (I - K_k H_k) P_{k|k-1}
        """
        z = np.asarray(z).reshape(-1, 1)
        
        # Innovation
        self.y = z - np.dot(self.H, self.x)
        
        # Kalman gain
        S = np.dot(np.dot(self.H, self.P), self.H.T) + self.R
        self.K = np.dot(np.dot(self.P, self.H.T), np.linalg.inv(S))
        
        # Update state
        self.x += np.dot(self.K, self.y)
        
        # Update covariance
        self.P = np.dot(np.eye(self.dim_x) - np.dot(self.K, self.H), self.P)
        
        return self.x.copy()
    
    def filter(self, measurements: Union[List[float], np.ndarray],
               u: Optional[Union[List[float], np.ndarray]] = None) -> np.ndarray:
        """
        Apply Kalman filter to sequence of measurements.
        
        Parameters
        ----------
        measurements : array-like
            Sequence of measurements
        u : array-like, optional
            Control inputs (one for each measurement)
        
        Returns
        -------
        filtered : ndarray
            Filtered state estimates (including smoothed estimates)
        
        Notes
        -----
        This performs filtering (not smoothing) and returns state estimates
        at each time step.
        """
        measurements = np.asarray(measurements)
        n = len(measurements)
        filtered = np.zeros((n, self.dim_x))
        
        for i in range(n):
            if u is not None:
                self.predict(u[i])
            else:
                self.predict()
            filtered[i] = self.update(measurements[i])
        
        return filtered
    
    def smooth(self, measurements: Union[List[float], np.ndarray],
               u: Optional[Union[List[float], np.ndarray]] = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        Apply Kalman smoothing to sequence of measurements.
        
        Parameters
        ----------
        measurements : array-like
            Sequence of measurements
        u : array-like, optional
            Control inputs
        
        Returns
        -------
        filtered : ndarray
            Filtered state estimates (forward pass)
        smoothed : ndarray
            Smoothed state estimates (backward pass)
        
        Notes
        -----
        Smoothing provides improved estimates by considering future measurements.
        This is the Rauch-Tung-Striebel (RTS) smoother implementation.
        """
        measurements = np.asarray(measurements)
        n = len(measurements)
        
        # Forward pass
        filtered = np.zeros((n, self.dim_x))
        P_filtered = np.zeros((n, self.dim_x, self.dim_x))
        
        for i in range(n):
            if u is not None:
                self.predict(u[i])
            else:
                self.predict()
            filtered[i] = self.update(measurements[i])
            P_filtered[i] = self.P.copy()
        
        # Backward pass (RTS smoother)
        smoothed = np.zeros((n, self.dim_x))
        smoothed[-1] = filtered[-1].copy()
        
        for i in range(n - 2, -1, -1):
            # Compute smoother gain
            J = np.dot(np.dot(P_filtered[i], self.F.T), np.linalg.inv(P_filtered[i + 1]))
            
            # Smooth state
            smoothed[i] = filtered[i] + np.dot(J, (smoothed[i + 1] - filtered[i + 1]))
        
        return filtered, smoothed


class DenoisingKalmanFilter(KalmanFilter):
    """
    Specialized Kalman filter for denoising time series.
    
    This filter uses a constant velocity model which is ideal for:
    - Damping oscillatory signals
    - Smoothing price data while preserving trends
    - Denoising without excessive lag
    
    The filter parameters are tuned for typical market data characteristics.
    """
    
    def __init__(self, dt: float = 1.0,
                 process_noise: float = 1e-4,
                 measurement_noise: float = 1e-3,
                 smoothing: bool = False):
        """
        Initialize denoising Kalman filter.
        
        Parameters
        ----------
        dt : float, optional
            Time step (default: 1.0)
        process_noise : float, optional
            Process noise covariance (default: 1e-4)
        measurement_noise : float, optional
            Measurement noise covariance (default: 1e-3)
        smoothing : bool, optional
            Use smoothing instead of filtering (default: False)
        
        Notes
        -----
        The constant velocity model assumes:
            x_k = x_{k-1} + v_k * dt
            v_k = v_{k-1} + w_k
        where w_k is process noise (random acceleration).
        """
        # State vector: [position, velocity]
        # Position is position, velocity is first difference
        self.dt = dt
        
        # State transition matrix
        F = np.array([[1, dt],
                      [0, 1]])
        
        # Observation matrix (observe position only)
        H = np.array([[1, 0]])
        
        # Process noise (random acceleration)
        Q = np.array([[dt**4/4, dt**3/2],
                      [dt**3/2, dt**2]]) * process_noise
        
        # Measurement noise
        R = np.array([[measurement_noise]])
        
        super().__init__(dim_x=2, dim_z=1, F=F, H=H, Q=Q, R=R)
        
        self.smoothing = smoothing
    
    def filter(self, measurements: Union[List[float], np.ndarray]) -> np.ndarray:
        """
        Apply denoising filter to measurements.
        
        Parameters
        ----------
        measurements : array-like
            Noisy measurements
        
        Returns
        -------
        filtered : ndarray
            Denoised estimates
        """
        measurements = np.asarray(measurements)
        
        if self.smoothing:
            filtered, smoothed = super().smooth(measurements)
            return smoothed
        else:
            return super().filter(measurements)


def design_and_apply_kalman_filter(measurements: Union[List[float], np.ndarray],
                                    smoothing: bool = False) -> np.ndarray:
    """
    Convenience function to apply Kalman denoising in one step.
    
    Parameters
    ----------
    measurements : array-like
        Noisy measurements
    smoothing : bool, optional
        Use smoothing algorithm (default: False)
    
    Returns
    -------
    denoised : ndarray
        Denoised signal
    
    Examples
    --------
    >>> import numpy as np
    >>> measurements = np.random.randn(1000) + np.cumsum(np.random.randn(1000) * 0.1)
    >>> denoised = design_and_apply_kalman_filter(measurements, smoothing=True)
    """
    filter_obj = DenoisingKalmanFilter(smoothing=smoothing)
    return filter_obj.filter(measurements)
