from constants import CONSTANTS


from datetime import timedelta


def get_met_from_shcourse(coarse):
    return CONSTANTS.IMAP_EPOCH + timedelta(seconds=coarse)
