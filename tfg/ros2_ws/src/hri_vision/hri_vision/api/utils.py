import numpy as np

def euclidean_distance(features_a, features_b):
    '''Calculates the euclidean distance between two vectors of the same size.
    
    Args:
        features_a (Array: float): First vector.
        features_b (Array: float): Second vector.
    
    Returns:
        distance (float): Euclidean distance.
    '''

    distance = np.linalg.norm(features_a - features_b)
    
    return distance

def normalized_cosine_similarity_distance(features_a, features_b):
    '''Calculates the normalized cosine distance between two vectors of the same size.
    
    Args:
        features_a (Array: float): First vector.
        features_b (Array: float): Second vector.
    
    Returns:
        distance (float): Normalized cosine distance.
    '''

    dot_product = np.dot(features_a, np.transpose(features_b))
    norm_a = np.linalg.norm(features_a)
    norm_b = np.linalg.norm(features_b)

    return (1 + (dot_product / (norm_a * norm_b))) / 2