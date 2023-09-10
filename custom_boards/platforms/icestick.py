from litex.build.generic_platform import *
from litex.build.lattice import LatticePlatform

_io = [
    ("user_led", 0, Pins("99"), IOStandard("LVCMOS33")),
    ("user_led", 1, Pins("98"), IOStandard("LVCMOS33")),
    ("user_led", 2, Pins("97"), IOStandard("LVCMOS33")),
    ("user_led", 3, Pins("96"), IOStandard("LVCMOS33")),
    ("user_led", 4, Pins("95"), IOStandard("LVCMOS33")),

    ("serial", 0,
        Subsignal("rx", Pins("9")),
        Subsignal("tx", Pins("8"),  Misc("PULLUP")),
        Subsignal("rts", Pins("7"), Misc("PULLUP")),
        Subsignal("cts", Pins("4"), Misc("PULLUP")),
        Subsignal("dtr", Pins("3"), Misc("PULLUP")),
        Subsignal("dsr", Pins("2"), Misc("PULLUP")),
        Subsignal("dcd", Pins("1"), Misc("PULLUP")),
        IOStandard("LVTTL"),
    ),

    ("irda", 0,
        Subsignal("rx", Pins("106")),
        Subsignal("tx", Pins("105")),
        Subsignal("sd", Pins("107")),
        IOStandard("LVCMOS33")
    ),

    ("spiflash", 0,
        Subsignal("cs_n", Pins("71"), IOStandard("LVCMOS33")),
        Subsignal("clk", Pins("70"), IOStandard("LVCMOS33")),
        Subsignal("mosi", Pins("67"), IOStandard("LVCMOS33")),
        Subsignal("miso", Pins("68"), IOStandard("LVCMOS33"))
    ),

    ("clk12", 0, Pins("21"), IOStandard("LVCMOS33"))
]

class Platform(LatticePlatform):
    default_clk_name = "clk12"
    default_clk_period = 83.333

    def __init__(self, device="ice40-hx1k", **kwargs):
        LatticePlatform.__init__(self, device + "-tq144", _io, **kwargs)    