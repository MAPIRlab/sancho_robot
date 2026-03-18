import pygame

def load(path):
    '''Loads an audio into memory.
    
    Args:
        path (str): The path to the audio source.
    
    Returns:
        sound (Sound): The loaded sound.
    '''

    pygame.mixer.init()
    sound = pygame.mixer.Sound(path)

    return sound

def play(sound, wait_for_end=False):
    '''Plays a sound.

    Note:
        The use of pygame is due it almost zero delay.

    Args:
        sound (Sound): Sound source.
        wait_for_end (bool): If true thread locks until audio ends.
    '''

    sound.play()
    if wait_for_end:
        pygame.time.wait(int(sound.get_length() * 1000))