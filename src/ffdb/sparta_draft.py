"""Authoritative Aug. 30, 2026 Sparta auction board transcription.

Each tuple is (player, auction_price). Team codes are exactly the board headers.
The two user-supplied full-board screenshots are the source of truth for this file.
"""

SPARTA_2026_DRAFT = {
    "MN": [
        ("Chris Olave",29),("Puka Nacua",62),("Saquon Barkley",53),("Jason Myers",2),("Rome Odunze",11),("Bo Nix",6),("Jameson Williams",12),("Chargers D/ST",1),("Matthew Stafford",2),("Juwan Johnson",2),("Keaton Mitchell",4),("RJ Harvey",3),("Jacory Croskey-Merritt",3),("Chuba Hubbard",3),("Josh Downs",2),("Matthew Golden",2),("Rachaad White",3),
    ],
    "TM": [
        ("Bijan Robinson",70),("James Cook",56),("Ladd McConkey",28),("Trevor Lawrence",8),("David Montgomery",14),("De'Zhaun Stribling",8),("Jaguars D/ST",1),("KC Concepcion",6),("Jake Bates",1),("Michael Wilson",2),("Tyler Shough",1),("Chigoziem Okonkwo",1),("Kaelon Black",1),("Packers D/ST",1),("Brian Robinson",1),("Emmett Johnson",1),("Greg Dulcich",1),
    ],
    "VV": [
        ("Jahmyr Gibbs",71),("Brandon Aubrey",3),("Josh Allen",26),("Sam LaPorta",10),("Patriots D/ST",3),("CeeDee Lamb",48),("D.J. Moore",20),("Patrick Mahomes",5),("Oronde Gadsden",1),("Michael Pittman",6),("David Njoku",1),("Travis Hunter",1),("Tyjae Spears",1),("Cyrus Allen",1),("Kaleb Johnson",1),("Jaydon Blue",1),("Dylan Sampson",1),
    ],
    "BE": [
        ("Trey McBride",28),("Malik Nabers",29),("Cameron Dicker",3),("Kyren Williams",34),("Luther Burden",24),("Dak Prescott",10),("Jaylen Warren",13),("Marvin Harrison Jr.",7),("TreVeyon Henderson",11),("Deebo Samuel",3),("Bhayshul Tuten",13),("Seahawks D/ST",1),("Blake Corum",9),("Quentin Johnston",7),("Isaiah Likely",6),("Romeo Doubs",1),("Mike Washington Jr.",2),
    ],
    "MC": [
        ("De'Von Achane",41),("Breece Hall",30),("Christian McCaffrey",55),("Kyle Pitts",8),("Drake Maye",11),("Justin Herbert",4),("DeVonta Smith",26),("Harold Fannin",4),("Brian Thomas Jr.",4),("Carnell Tate",10),("Tyler Loop",1),("Vikings D/ST",1),("Jordyn Tyson",1),("Malik Washington",1),("Jakobi Meyers",1),("Woody Marks",1),("Chris Bell",1),
    ],
    "ANT": [
        ("Amon-Ra St. Brown",61),("Kenneth Walker III",40),("Jeremiyah Love",31),("George Kittle",5),("Jared Goff",6),("Terry McLaurin",9),("Tee Higgins",21),("Mike Evans",7),("Dalton Kincaid",4),("Steelers D/ST",1),("Harrison Butker",1),("Jordan Mason",9),("Tyler Allgeier",1),("Braelon Allen",1),("Jerry Jeudy",1),("Kayshon Boutte",1),("Ray Davis",1),
    ],
    "JU": [
        ("Jonathan Taylor",55),("Derrick Henry",41),("Tyler Warren",16),("Garrett Wilson",23),("Jaylen Waddle",24),("Jaxson Dart",7),("Rico Dowdle",6),("Caleb Williams",5),("Jonathon Brooks",6),("Jalen Coker",2),("Harrison Mevis",1),("Terrance Ferguson",2),("Wan'Dale Robinson",4),("Kenneth Gainwell",2),("Chris Rodriguez",4),("Lions D/ST",1),("Tre Tucker",1),
    ],
    "JD": [
        ("Ja'Marr Chase",65),("Tetairoa McMillan",19),("Jaxon Smith-Njigba",64),("Jalen Hurts",7),("Quinshon Judkins",17),("Rhamondre Stevenson",12),("Dalton Schultz",1),("Ravens D/ST",1),("J.K. Dobbins",5),("Jake Elliott",1),("Malik Willis",1),("Ja'Kobi Lane",1),("Dontayvion Wicks",2),("Xavier Worthy",2),("Devin Neal",1),("Kendre Miller",1),("Pat Bryant",1),
    ],
    "SR": [
        ("Broncos D/ST",2),("Brock Bowers",35),("A.J. Brown",54),("George Pickens",31),("Parker Washington",30),("MarShawn Lloyd",16),("Josh Jacobs",5),("Brock Purdy",5),("Davante Adams",14),("Eddy Pineiro",1),("Jonah Coleman",1),("Samaje Perine",1),("Jake Ferguson",1),("Makai Lemon",1),("Tank Bigsby",1),("Hunter Henry",1),("T.J. Hockenson",1),
    ],
    "JP": [
        ("Texans D/ST",3),("Ka'imi Fairbairn",2),("Colston Loveland",20),("Justin Jefferson",56),("Omarion Hampton",40),("Zay Flowers",29),("Travis Etienne",19),("Joe Burrow",11),("Christian Watson",8),("DK Metcalf",4),("Brenton Strange",1),("Andres Borregales",1),("Kyler Murray",1),("Khalil Shakir",2),("Kimani Vidal",1),("Alvin Kamara",1),("Adonai Mitchell",1),
    ],
    "ME": [
        ("Chase Brown",45),("Rams D/ST",4),("Jadarian Price",18),("Cam Little",3),("D'Andre Swift",28),("Jayden Daniels",6),("Drake London",41),("Tucker Kraft",11),("Rashee Rice",28),("Dallas Goedert",3),("Stefon Diggs",3),("Zach Charbonnet",3),("Jordan Addison",1),("Rashid Shaheed",1),("Kyle Monangai",3),("Keenan Allen",1),("Denzel Boston",1),
    ],
    "MM": [
        ("Lamar Jackson",14),("Bucky Irving",21),("Ashton Jeanty",30),("Emeka Egbuka",20),("Nico Collins",35),("Mark Andrews",3),("Cam Skattebo",14),("Javonte Williams",26),("Tony Pollard",6),("Eagles D/ST",2),("Jayden Reed",1),("Alec Pierce",4),("Courtland Sutton",3),("Travis Kelce",4),("Chris Godwin",5),("Aaron Jones",1),("Chris Boswell",10),
    ],
}

assert len(SPARTA_2026_DRAFT) == 12
assert all(len(roster) == 17 for roster in SPARTA_2026_DRAFT.values())
assert all(sum(price for _, price in roster) == 200 for roster in SPARTA_2026_DRAFT.values())
