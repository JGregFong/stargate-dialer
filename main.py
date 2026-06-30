import glyph_database
import time
import random

address_list = glyph_database.address_list
glyphs = glyph_database.glyphs
speed = 15


def print_hi(name):
    # Use a breakpoint in the code line below to debug your script.
    print(f'Hi, {name}')  # Press Ctrl+F8 to toggle the breakpoint.
    time.sleep(random.randint(1, 3))
    if check_valid_destination("Earth"):
        dial_address("Earth")


def dial_address(address):
    if address in address_list:
        for symbol in address_list[address]:
            print(symbol, glyphs[symbol])
        print(0, glyphs[0])
    else:
        print("Invalid address")


def dial(dial_mode, max_number):
    symbol_list = []

    if dial_mode == "Local Dialing":
        for symbol in range(6):
            symbol_list.append(input(f"Enter symbol index number {symbol+1}"))

        if match_address(symbol_list):
            symbol_list.append(0)
            establish_wormhole()
        else:
            fail_connection()


    if 8 >= max_number > 6:
        for symbol in range(max_number):
            glyph = input(f"Enter symbol index number {symbol+1}")
            symbol_list.append(glyph)
            print("Chevron")

        if match_address(symbol_list):
            print("Chevron {}".format(max_number) + " Locked")
            establish_wormhole()
        else:
            print("Chevron {}".format(max_number) + " will not engage.")
            fail_connection()


    else:
        print("Invalid number")


def randomized_dialing():
    print("Randomizing Dialing")
    remaining_glyphs = glyph_database.glyph_numbers
    randomized_address = []
    for item in range(6):
        choice = random.choice(remaining_glyphs)
        randomized_address.append(choice)
        remaining_glyphs.remove(choice)

    if match_address(randomized_address):
        establish_wormhole()
    else:
        fail_connection()

# Checks input address against address list
def match_address(input_address):
    for name, address in address_list.items():
        if address == input_address:
            return True

    return False



def check_valid_destination(destination):
    for candidate in address_list:
        if destination == candidate:
            print(f"{destination} has a valid address.")
            return True
    return False



def establish_wormhole():
    print("Wormhole Established")


def fail_connection():
    print("Wormhole has failed to establish")
    print("Connection Failed")


if __name__ == '__main__':
    print_hi('PyCharm')
    print("Stargate Dialing Program")

    print("1. Manual Dialing")
    print("2. Look up Address")


    #planet = input("Please enter your destination: ")
