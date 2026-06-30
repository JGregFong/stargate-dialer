glyphs = ["Earth",
          "Crater", "Virgo", "Bootes", "Centaurus", "Libra", "Serpens Caput", "Norma", "Scorpio", "Cra", "Scutum",
          "Sagittarius", "Aquila", "Mic", "Capricorn", "Pisces Austrinus", "Equuleus", "Aquarius", "Pegasus",
          "Sculptor", "Pisces",
          "Andromeda", "Triangulum", "Aries", "Perseus", "Cetus", "Taurus", "Auriga", "Eridanus", "Orion",
          "Canis Minor",
          "Monoceros", "Gemini", "Hydra", "Lynx", "Cancer", "Sextans", "Leo Minor", "Leo"]

glyph_numbers = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28,
                 29, 30, 31, 32, 33, 34, 35, 36, 37, 38]

address_list = {
    "Earth": [27, 26, 5, 36, 11, 28],
    "Abydos": [26, 6, 14, 31, 11, 29],
    "Atlantis": [18, 20, 1, 15, 14, 7, 19],
    "Castiana": [28, 2, 5, 8, 11, 15],
    "Chulak": [8, 1, 22, 14, 36, 19],
    "Destiny": [5, 27, 15, 3, 35, 16, 4, 33],
    "Edora": [27, 37, 34, 8, 14, 2],
    "Euronda": [29, 26, 8, 6, 17, 15],
    "Juna": [28, 7, 17, 21, 3, 24],
    "Kallana": [5, 15, 7, 2, 25, 24],
    "Kheb": [25, 34, 5, 7, 22, 13],
    "Klorel's Hatak": [2, 31, 15, 7, 9, 11],
    "Martin Lloyd's Homeworld": [23, 11, 31, 6, 10, 33],
    "NID Offworld Base": [37, 27, 14, 34, 2, 18],
    "Othala": [10, 26, 22, 15, 32, 2, 8],
    "P2X-555": [27, 7, 15, 32, 12, 30],
    "P34-353J": [37, 8, 27, 14, 34, 2],
    "Sahal": [28, 17, 18, 19, 20, 21],
    "Vagon Brei": [2, 7, 1, 11, 18, 29]

}

address_database = {
    "Earth":    {"Address": [27, 26, 5, 36, 11, 28], "Locked": False, "Active": True, "Notes": "", "Source": ""},
    "Abydos":   {"Address": [26, 6, 14, 31, 11, 29], "Locked": False, "Active": True, "Notes": "", "Source": ""},
    "Atlantis": {"Address": [18, 20, 1, 15, 14, 7, 19], "Locked": False, "Active": True, "Notes": "", "Source": ""},
    "Camelot":  {"Address": [19, 1, 34, 7, 25, 14], "Locked": False, "Active": True, "Notes": "", "Source": ""},
    "Castiana": {"Address": [28,2,5,8,11,15], "Locked": False, "Active": True, "Notes": "", "Source": ""},
    "Chulak":   {"Address": [8, 1, 22, 14, 36, 19], "Locked": False, "Active": True, "Notes": "", "Source": ""},
    "Clava Thessara Infinitas [1]":
                {"Address": [13,20,15,10,29,8], "Locked": False, "Active": True, "Notes": "", "Source": ""},
    "Clava Thessara Infinitas [2]":
                {"Address": [25,19,34,31,22,3], "Locked": False, "Active": True, "Notes": "", "Source": ""},
    "Destiny":  {"Address": [5, 27, 15, 3, 35, 16, 4, 33], "Locked": False, "Active": True, "Notes": "", "Source": ""},
    "Edora":    {"Address": [27, 37, 34, 8, 14, 2], "Locked": False, "Active": True, "Notes": "", "Source": ""},
    "Euronda":  {"Address": [29, 26, 8, 6, 17, 15], "Locked": False, "Active": True, "Notes": "", "Source": ""},
    "Juna":     {"Address": [28, 7, 17, 21, 3, 24], "Locked": False, "Active": True, "Notes": "", "Source": ""},
    "Kallana":  {"Address": [5, 15, 7, 2, 25, 24], "Locked": False, "Active": True, "Notes": "", "Source": ""},
    "Kheb":     {"Address": [25, 34, 5, 7, 22, 13], "Locked": False, "Active": True, "Notes": "", "Source": ""},
    "Klorel's Hatak":
                {"Address": [2, 31, 15, 7, 9, 11], "Locked": False, "Active": True, "Notes": "", "Source": ""},
    "Martin Lloyd's Homeworld":
                {"Address": [23, 11, 31, 6, 10, 33], "Locked": False, "Active": True, "Notes": "", "Source": ""},
    "NID Offworld Base":
                {"Address": [37, 27, 14, 34, 2, 18], "Locked": False, "Active": True, "Notes": "", "Source": ""},
    "Othala":   {"Address": [10, 26, 22, 15, 32, 2, 8], "Locked": False, "Active": True, "Notes": "", "Source": ""},
    "P2X-555":  {"Address": [27, 7, 15, 32, 12, 30], "Locked": False, "Active": True, "Notes": "", "Source": ""},
    "P34-353J": {"Address": [37, 8, 27, 14, 34, 2], "Locked": False, "Active": True, "Notes": "", "Source": ""},
    "P3W-451":  {"Address": [18, 7, 4, 36, 25, 15], "Locked": True, "Active": True, "Notes": "", "Source": ""},
    "P3X-118":  {"Address": [8, 25, 33, 36, 16, 20], "Locked": True, "Active": True, "Notes": "", "Source": ""},
    "P3X-562":  {"Address": [2, 27, 8, 34, 23, 14], "Locked": False, "Active": True, "Notes": "", "Source": ""},
    "P3X-984":  {"Address": [28, 4, 35, 5, 23, 15], "Locked": False, "Active": True, "Notes": "", "Source": ""},
    "P9C-372":  {"Address": [24, 7, 17, 28, 3, 21], "Locked": True, "Active": True, "Notes": "", "Source": ""},
    "PB5-926":  {"Address": [11, 35, 22, 17, 6, 26], "Locked": False, "Active": True, "Notes": "", "Source": ""},
    "Praclarush Taonas": 
                {"Address": [34, 2, 30, 28, 4, 16], "Locked": False, "Active": False, "Notes": "", "Source": ""},
    "Sahal":    {"Address": [28, 17, 18, 19, 20, 21], "Locked": False, "Active": True, "Notes": "", "Source": ""},
    "Sangreal Planet": 
                {"Address": [29, 18, 33, 8, 32, 17], "Locked": False, "Active": True, "Notes": "", "Source": ""},
    "Tartarus": {"Address": [32, 27, 22, 25, 15, 30], "Locked": False, "Active": True, "Notes": "", "Source": ""},
    "Tollan":   {"Address": [5, 32, 26, 36, 10, 17], "Locked": False, "Active": False, "Notes": "", "Source": ""},
    "Tollana":  {"Address": [3, 28, 7, 21, 17, 24], "Locked": False, "Active": False, "Notes": "", "Source": ""},
    "Unnamed Planet": 
                {"Address": [8, 17, 26, 14, 20, 35], "Locked": False, "Active": True, "Notes": "", "Source": ""},
    "Vagon Brei":
                {"Address": [2, 7, 1, 11, 18, 29], "Locked": False, "Active": True, "Notes": "", "Source": ""}
}
