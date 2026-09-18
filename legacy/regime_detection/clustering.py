"""
Unsupervised Regime Clustering

This module provides unsupervised learning methods to identify market regimes
without prior labels, using K-Means and DBSCAN clustering.
"""

import numpy as np
from typing import Dict, List, Tuple
from sklearn.cluster import KMeans, DBSCAN
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score, calinski_harabasz_score
from sklearn.decomposition import PCA
import matplotlib.pyplot as plt


class RegimeClustering:
    """
    Unsupervised clustering of market regimes.
    
    This module uses K-Means and DBSCAN to identify different market states
    based on statistical features of returns.
    
    Parameters
    ----------
    n_clusters : int, optional
        Number of clusters for K-Means. Default: 3
    eps : float, optional
        Maximum distance between samples for DBSCAN. Default: 0.5
    min_samples : int, optional
        Minimum samples per cluster for DBSCAN. Default: 5
    n_features : int, optional
        Number of features to use for clustering. Default: 5
    
    Examples
    --------
    >>> clusterer = RegimeClustering(n_clusters=3)
    >>> labels = clusterer.fit_predict(returns)
    >>> clusterer.visualize_clusters(returns)
    """
    
    def __init__(self, n_clusters: int = 3, eps: float = 0.5, 
                 min_samples: int = 5, n_features: int = 5):
        self.n_clusters = n_clusters
        self.eps = eps
        self.min_samples = min_samples
        self.n_features = n_features
        self.scaler = StandardScaler()
        self.kmeans = KMeans(n_clusters=n_clusters, random_state=42)
        self.dbscan = DBSCAN(eps=eps, min_samples=min_samples)
        self.labels = None
        self.centroids = None
    
    def extract_features(self, returns: np.ndarray, 
                         volumes: np.ndarray = None) -> np.ndarray:
        """
        Extract features for clustering.
        
        Parameters
        ----------
        returns : np.ndarray
            Returns series
        volumes : np.ndarray, optional
            Volume series
        
        Returns
        -------
        features : np.ndarray
            Feature matrix (n_samples, n_features)
        """
        features = []
        
        for i in range(len(returns)):
            window_start = max(0, i - self.n_features + 1)
            window = returns[window_start:i+1]
            
            if len(window) < self.n_features:
                # Use trailing window
                window = returns[-self.n_features:]
            
            feature = [
                np.mean(window),          # Mean return
                np.std(window),           # Volatility
                np.max(window),           # Maximum return
                np.min(window),           # Minimum return
                np.mean(np.abs(window)),  # Average absolute return
                np.percentile(window, 25),  # 25th percentile
                np.percentile(window, 75),  # 75th percentile
            ]
            
            if volumes is not None and i < len(volumes):
                feature.append(volumes[i] / (np.mean(volumes) + 1e-10))
            
            features.append(feature)
        
        return np.array(features)
    
    def fit_predict(self, returns: np.ndarray, volumes: np.ndarray = None) -> np.ndarray:
        """
        Fit clustering model and predict labels.
        
        Parameters
        ----------
        returns : np.ndarray
            Returns series
        volumes : np.ndarray, optional
            Volume series
        
        Returns
        -------
        labels : np.ndarray
            Cluster labels for each time point
        """
        # Extract features
        features = self.extract_features(returns, volumes)
        
        # Standardize features
        features_scaled = self.scaler.fit_transform(features)
        
        # Fit K-Means
        self.labels = self.kmeans.fit_predict(features_scaled)
        
        # Get centroids
        self.centroids = self.kmeans.cluster_centers_
        
        return self.labels
    
    def fit_predict_dbscan(self, returns: np.ndarray, volumes: np.ndarray = None) -> np.ndarray:
        """
        Fit DBSCAN and predict labels.
        
        Parameters
        ----------
        returns : np.ndarray
            Returns series
        volumes : np.ndarray, optional
            Volume series
        
        Returns
        -------
        labels : np.ndarray
            Cluster labels for each time point
        """
        # Extract features
        features = self.extract_features(returns, volumes)
        
        # Standardize features
        features_scaled = self.scaler.fit_transform(features)
        
        # Fit DBSCAN
        self.labels = self.dbscan.fit_predict(features_scaled)
        
        return self.labels
    
    def get_cluster_centers(self) -> np.ndarray:
        """
        Get cluster centroids (in original feature space).
        
        Returns
        -------
        centroids : np.ndarray
            Cluster centroids
        """
        if self.centroids is None:
            raise ValueError("Model not fitted. Call fit_predict() first.")
        
        return self.scaler.inverse_transform(self.centroids)
    
    def get_cluster_statistics(self, returns: np.ndarray) -> Dict[int, Dict]:
        """
        Get statistics for each cluster.
        
        Parameters
        ----------
        returns : np.ndarray
            Returns series
        
        Returns
        -------
        stats : dict
            Statistics for each cluster
        """
        if self.labels is None:
            raise ValueError("Model not fitted. Call fit_predict() first.")
        
        stats = {}
        
        for cluster in np.unique(self.labels):
            mask = self.labels == cluster
            cluster_returns = returns[mask]
            
            stats[cluster] = {
                'count': len(cluster_returns),
                'mean': np.mean(cluster_returns),
                'std': np.std(cluster_returns),
                'min': np.min(cluster_returns),
                'max': np.max(cluster_returns),
                'median': np.median(cluster_returns)
            }
        
        return stats
    
    def calculate_silhouette_score(self, returns: np.ndarray, volumes: np.ndarray = None) -> float:
        """
        Calculate silhouette score for clustering quality.
        
        Parameters
        ----------
        returns : np.ndarray
            Returns series
        volumes : np.ndarray, optional
            Volume series
        
        Returns
        -------
        score : float
            Silhouette score (range: -1 to 1)
        """
        if self.labels is None:
            raise ValueError("Model not fitted. Call fit_predict() first.")
        
        features = self.extract_features(returns, volumes)
        features_scaled = self.scaler.transform(features)
        
        return silhouette_score(features_scaled, self.labels)
    
    def calculate_calinski_harabasz_score(self, returns: np.ndarray, volumes: np.ndarray = None) -> float:
        """
        Calculate Calinski-Harabasz score.
        
        Parameters
        ----------
        returns : np.ndarray
            Returns series
        volumes : np.ndarray, optional
            Volume series
        
        Returns
        -------
        score : float
            Calinski-Harabasz score
        """
        if self.labels is None:
            raise ValueError("Model not fitted. Call fit_predict() first.")
        
        features = self.extract_features(returns, volumes)
        features_scaled = self.scaler.transform(features)
        
        return calinski_harabasz_score(features_scaled, self.labels)
    
    def visualize_clusters(self, returns: np.ndarray, volumes: np.ndarray = None,
                           figsize: Tuple[int, int] = (16, 6)):
        """
        Visualize clustering results.
        
        Parameters
        ----------
        returns : np.ndarray
            Returns series
        volumes : np.ndarray, optional
            Volume series
        figsize : tuple, optional
            Figure size
        """
        if self.labels is None:
            raise ValueError("Model not fitted. Call fit_predict() first.")
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)
        
        # Plot returns with cluster colors
        unique_labels = np.unique(self.labels)
        colors = plt.cm.tab10(np.linspace(0, 1, len(unique_labels)))
        
        for label, color in zip(unique_labels, colors):
            mask = self.labels == label
            ax1.scatter(np.where(mask)[0], returns[mask], c=[color], 
                       label=f'Cluster {label}', alpha=0.6, s=30)
        
        ax1.set_title('Returns with Cluster Labels')
        ax1.set_xlabel('Time')
        ax1.set_ylabel('Returns')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Plot PCA visualization
        features = self.extract_features(returns, volumes)
        features_scaled = self.scaler.transform(features)
        
        pca = PCA(n_components=2)
        pca_features = pca.fit_transform(features_scaled)
        
        for label, color in zip(unique_labels, colors):
            mask = self.labels == label
            ax2.scatter(pca_features[mask, 0], pca_features[mask, 1], 
                       c=[color], label=f'Cluster {label}', alpha=0.6, s=30)
        
        ax2.set_title('PCA Visualization')
        ax2.set_xlabel('PC1')
        ax2.set_ylabel('PC2')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.show()
    
    def get_transition_matrix(self) -> np.ndarray:
        """
        Get transition matrix between clusters.
        
        Returns
        -------
        transition_matrix : np.ndarray
            Transition probability matrix
        """
        if self.labels is None:
            raise ValueError("Model not fitted. Call fit_predict() first.")
        
        n_clusters = len(np.unique(self.labels))
        transition_matrix = np.zeros((n_clusters, n_clusters))
        
        for i in range(len(self.labels) - 1):
            from_cluster = self.labels[i]
            to_cluster = self.labels[i + 1]
            transition_matrix[from_cluster, to_cluster] += 1
        
        # Convert to probabilities
        row_sums = transition_matrix.sum(axis=1)
        row_sums[row_sums == 0] = 1  # Avoid division by zero
        transition_matrix = transition_matrix / row_sums[:, np.newaxis]
        
        return transition_matrix
    
    def get_regime_duration(self) -> Dict[int, int]:
        """
        Get duration of each regime in periods.
        
        Returns
        -------
        durations : dict
            Dictionary with cluster IDs as keys and durations as values
        """
        if self.labels is None:
            raise ValueError("Model not fitted. Call fit_predict() first.")
        
        durations = {}
        
        for label in np.unique(self.labels):
            mask = self.labels == label
            consecutive = 0
            
            for i in range(len(self.labels)):
                if self.labels[i] == label:
                    consecutive += 1
                else:
                    if consecutive > 0:
                        durations[label] = durations.get(label, 0) + consecutive
                        consecutive = 0
            
            if consecutive > 0:
                durations[label] = durations.get(label, 0) + consecutive
        
        return durations


class ElbowMethod:
    """
    Elbow method to determine optimal number of clusters.
    
    This helps identify the optimal number of clusters by calculating
    within-cluster sum of squares for different cluster counts.
    
    Parameters
    ----------
    n_range : int, optional
        Range of cluster counts to test. Default: 10
    
    Examples
    --------
    >>> elbow = ElbowMethod(n_range=10)
    >>> elbow.plot_elbow_curve(returns, volumes)
    """
    
    def __init__(self, n_range: int = 10):
        self.n_range = n_range
    
    def calculate_wcss(self, features: np.ndarray, n_clusters: int) -> float:
        """
        Calculate within-cluster sum of squares (WCSS).
        
        Parameters
        ----------
        features : np.ndarray
            Feature matrix
        n_clusters : int
            Number of clusters
        
        Returns
        -------
        wcss : float
            Within-cluster sum of squares
        """
        kmeans = KMeans(n_clusters=n_clusters, random_state=42)
        labels = kmeans.fit_predict(features)
        centroids = kmeans.cluster_centers_
        
        wcss = 0.0
        for i in range(n_clusters):
            cluster_features = features[labels == i]
            cluster_centroid = centroids[i]
            wcss += np.sum((cluster_features - cluster_centroid) ** 2)
        
        return wcss
    
    def plot_elbow_curve(self, features: np.ndarray, figsize: Tuple[int, int] = (10, 6)):
        """
        Plot elbow curve.
        
        Parameters
        ----------
        features : np.ndarray
            Feature matrix
        figsize : tuple, optional
            Figure size
        """
        wcss_values = []
        
        for n_clusters in range(1, self.n_range + 1):
            wcss = self.calculate_wcss(features, n_clusters)
            wcss_values.append(wcss)
        
        fig, ax = plt.subplots(figsize=figsize)
        
        ax.plot(range(1, self.n_range + 1), wcss_values, 'bo-')
        ax.set_title('Elbow Method for Optimal k')
        ax.set_xlabel('Number of Clusters')
        ax.set_ylabel('Within-Cluster Sum of Squares (WCSS)')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.show()
