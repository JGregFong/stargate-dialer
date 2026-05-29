import glyph_database
import time
import random

address_list = glyph_database.address_list
glyphs = glyph_database.glyphs

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

def manual_dial (number):
    symbol_list =[]
    if 8 >= number >= 6:
        for symbol in range(number):
            symbol_list.append(input(f"Enter symbol number {symbol}"))


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

    check_valid_destination("Earth")

def match_address(destination):

    for name, address in address_list.items():
        if address == destination:
            print(f"Address matched. {name}")
            return True

    return False


def check_valid_destination(destination):
    for candidate in address_list:
        if destination == candidate:
            print(f"{destination} has a valid address.")
            return True
    return False


def point_of_origin():
    return 0

if __name__ == '__main__':
    print_hi('PyCharm')
    print("Stargate Dialing Program")

    print("1. Manual Dialing")
    print("2. Dial Address From Database")



    planet = input("Please enter your destination: ")
