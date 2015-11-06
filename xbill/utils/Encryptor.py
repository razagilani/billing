from Crypto.Cipher import AES
from xbill import settings
import base64

class Encryptor:
    @staticmethod
    def __apply_padding(str):
        '''
        In order to encrypt a string with AES, the sting has
        to be a multiple of block_size long. This method adds the 
        neccessary padding
        '''
        bs=settings.ENCRYPTION['block_size']
        padding_amount=(bs - len(str) % bs)
        return str + (padding_amount * settings.ENCRYPTION['padding'])

    @staticmethod
    def encrypt(message):
        '''
        This method applies padding to the message,
        encrypts the message based on salt
        and returns the base64 encoded string
        '''
        cipher=AES.new(settings.ENCRYPTION['salt'])
        encr=cipher.encrypt(Encryptor.__apply_padding(message))
        return base64.b64encode(encr)
        
        
    @staticmethod
    def decrypt(message):
        '''
        This method decodes the encoded message based on salt
        and removes the padding
        '''
        cipher=AES.new(settings.ENCRYPTION['salt'])
        decrypt=cipher.decrypt(base64.b64decode(message))
        return decrypt.rstrip(settings.ENCRYPTION['padding'])