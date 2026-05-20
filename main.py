import glyph_database

address_list = glyph_database.address_list
glyphs = glyph_database.glyphs

def print_hi(name):
    # Use a breakpoint in the code line below to debug your script.
    print(f'Hi, {name}')  # Press Ctrl+F8 to toggle the breakpoint.
    dial_address("Earth")





def dial_address(address):
    if address in address_list:
        for symbol in address_list[address]:
            print(symbol, glyphs[symbol])

    else:
        print("Invalid address")

def manual_dial (number):
    symbol_list =[]
    if 9 >= number >= 7:
        for symbol in range(number):
            symbol_list.append(input(f"Enter symbol number {symbol}"))


def check_address(address):
    if address in address_list:
        return True
    else:
        return False

if __name__ == '__main__':
    print_hi('PyCharm')