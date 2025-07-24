import numpy as np
import pickle

people = {}
size = {}

def save(fileName):
    '''Saves the learned data to a file.
    
    Args:
        fileName (str): File name.
    '''

    global people
    global size

    with open(fileName, 'wb') as fp:
        pickle.dump(people, fp)

def load(fileName):
    '''Loads the learned data from a file.
    
    Args:
        fileName (str): File name.
    '''

    global people
    global size
    
    try:
        with open(fileName, 'rb') as fp:
            people = pickle.load(fp)

        for className in people:
            size[className] = 1
        
        if len(people) > 0:
            printPeople()
    except FileNotFoundError:
        people = {}

def printPeople():
    '''Prints the names of the existing people.'''

    global people
    global size
    
    print("Personas que conozco:")
    for key in people:
        print(key)

def euclideanDistance(featuresA, featuresB):
    '''Calculates the euclidean distance between two vectors of the same size.
    
    Args:
        featuresA (Array: float): First vector.
        featuresB (Array: float): Second vector.
    
    Returns:
        distance (float): Euclidean distance.
    '''

    return np.linalg.norm(featuresA - featuresB)

def normalizedCosineSimilarityDistance(featuresA, featuresB):
    '''Calculates the normalized cosine distance between two vectors of the same size.
    
    Args:
        featuresA (Array: float): First vector.
        featuresB (Array: float): Second vector.
    
    Returns:
        distance (float): Normalized cosine distance.
    '''

    dotProduct = np.dot(featuresA, np.transpose(featuresB))
    normA = np.linalg.norm(featuresA)
    normB = np.linalg.norm(featuresB)

    return (1 + (dotProduct / (normA * normB))) / 2

def classifyFace(newFeatures):
    '''Given a feature vector, gives the closest class.
    
    Args:
        newFeatures (Array: float): Feature vector.
    
    Returns:
        closestClass (str): The name of the closest class.
        closesDistance (float): The normalized cosine distance to the closestClass.
        position (int): The position of the vector in the array of vectors of the class that
            was the closest to the given vector.
    '''

    global people
    global size
    
    closestClass = None
    closestDistance = 0
    position = 0

    if not people:
        return closestClass, closestDistance, position

    for className, features in people.items():
        distance = normalizedCosineSimilarityDistance(newFeatures, features)

        if distance > closestDistance:
            closestDistance = distance
            closestClass = className

    return closestClass, closestDistance, position

def refineClass(className, features, position):
    '''Makes the feature vector of a class more precise.

    Args:
        className (str): The class.
        features (Array: float): The new feature vector.
        position (int): Unused.
    '''

    global people
    global size

    newSize = size[className] + 1
    size[className] = newSize

    people[className] = (people[className] * (newSize - 1) + features) / newSize

def addFeatures(className, features):
    '''Makes the feature vector of a class more precise.
    
    Args:
        className (str): The class.
        features (Array: float): The new feature vector.
    '''

    refineClass(className, features, 0)

def addClass(className, features):
    '''Adds a new class with a unique feature vector.

    Args:
        className (str): The class.
        features (Array: float): The feature vector.
    '''

    global people
    global size
    
    alreadyKnown = className in people

    if alreadyKnown:
        addFeatures(className, features)
    else:
        people[className] = features
        size[className] = 1
    
    return alreadyKnown

def deleteClass(className):
    '''Removes a class.
    
    Args:
        className (str): The class.
    '''

    global people
    global size
    
    people.pop(className)