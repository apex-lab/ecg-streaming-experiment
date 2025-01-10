from psychopy import visual

def _display_text(win, txt):
    msg = visual.TextStim(
        win,
        text = txt,
        pos = (0,0),
        wrapWidth = win.size[0]
        )
    msg.draw()
    win.flip()

def _wait_for_spacebar(kb):
    kb.waitKeys(keyList = ['space'], clear = True)

def _show_instructions(win, kb, msg):
    msg += '\n\n(Press the spacebar to continue.)'
    _display_text(win, msg)
    _wait_for_spacebar(kb)

def fixation_cross(win):
    _display_text(win, '+')


def show_opening_instructions(win, kb):

    msg = '''
    Welcome, and thank you for participating in our study!
    '''
    _show_instructions(win, kb, msg)

    msg = '''
    In this experiment, we will play you sequences of tones.

    These tone sequences will either sound more like a single, galloping rhythm
    consisting of two tones, like ABA-ABA (where - denotes a space),

    or they will sound more like two metronome-like rhythms playing simultaneously
    but at different tempos, like A-A-A-A and B---B---.

    Each tone sequence is ambiguous, so it could sound more to you like    either possibility.
    '''
    _show_instructions(win, kb, msg)

    msg = '''
    Each tone sequence will last about 10 seconds, after which we will ask you
    which possibility ('galloping' ABA-ABA vs. regular A-A & B---B) you heard.
    You will be able to respond using the keyboard in front of you.

    You may not hear the same thing for the entire sequence. (In other words,
    your perception may switch.) If this is the case, please respond which
    you heard more by the end of the trial.

    We are interested in how often you hear the two possible percepts as
    we vary the frequencies of the tones, and whether your perception
    influences your heart rate.
    '''
    _show_instructions(win, kb, msg)

    msg = '''
    If you have any questions, please ask the experimenter now!
    '''
    _show_instructions(win, kb, msg)

    msg = '''
    The experiment will begin after you press the space bar.
    '''
    _show_instructions(win, kb, msg)



def show_midpoint_instructions(win, kb):
    msg = '''
    You have completed the first task!

    Now you will complete a task to assess whether you can feel your heartbeat.
    '''
    _show_instructions(win, kb, msg)
    msg = '''
    On each trial of the next task, you will hear a sequence of tones.

    The tones will either play in synchrony with your heartbeat,
    or they will play out-of-phase (i.e. delayed relative to) your heartbeat.

    You will hear each sequence for about 10 seconds, and then you will
    be asked whether you thought it was in sync with your heart.
    '''
    _show_instructions(win, kb, msg)
    msg = '''
    Please do not 'cheat' by feeling your pulse with your hand.
    Try to rely only on internal sensations.

    This task is very difficult, and it is expected that you'll
    have to guess often. Just try to do the best that you can.
    '''
    _show_instructions(win, kb, msg)
    msg = '''
    Please ask the experimenter if you have any questions.

    Otherwise, you may begin by pressing space.
    '''
    _show_instructions(win, kb, msg)


def show_closing_instructions(win, kb):
    msg = '''
    You have completed the experiment!
    '''
    _show_instructions(win, kb, msg)
    msg = '''
    Thank you for participating.

    Please let the experimenter know you're done.
    '''
    _show_instructions(win, kb, msg)

def solicit_2AFC_streaming(win, kb):
    msg = '''
    Did you primarily hear one, galloping sequence (ABA-ABA)
    or two, metronome-like sequences (A-A-A & B---B---B).

    Press the left arrow key for "galloping" and right arrow for "metronome."
    '''
    _display_text(win, msg)
    keys = kb.waitKeys(keyList = ['left', 'right'], clear = True)
    resp = keys[0].name
    if resp == 'left':
        return 'coherent'
    else:
        return 'streaming'

def solicit_2AFC_discrimination(win, kb):
    msg = '''
    Was the tone in sync with your heartbeat?

    Press the left arrow key for "yes" and right arrow for "no."
    '''
    _display_text(win, msg)
    keys = kb.waitKeys(keyList = ['left', 'right'], clear = True)
    resp = keys[0].name
    if resp == 'left':
        return 'yes'
    else:
        return 'no'
