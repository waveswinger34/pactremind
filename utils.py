#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4


AIRTEL = 'Airtel'
MTN = 'MTN'
VODAFONE = 'Vodafone'
TIGO = 'Tigo'
EXPRESSO = 'Expresso'

MESSAGES = ['Praying that you feel better.  Please finish your malaria drugs.',
            'Please remember to take your malaria drugs.',
            ('Please remember to take your malaria drugs. '
             'The malaria will survive if you do not take all of the pills.')]

def network (phone_number):
    xs = phone_number[:3]
    if xs:
        if xs == '026':
            return AIRTEL
        elif xs == '024' or xs == '054':
            return MTN
        elif xs == '020':
            return VODAFONE
        elif xs == '027' or xs == '057':
            return TIGO
        elif xs == '028':
            return EXPRESSO
    return 'Unknown'

