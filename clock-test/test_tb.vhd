library ieee;
use ieee.std_logic_1164.all;
 
entity DeltaCyclesTb is
end entity;
 
architecture sim of DeltaCyclesTb is
 
    signal Sig1 : std_logic := '0';
    signal Sig2 : std_logic;
 
begin
 
    process is
    begin
        Sig1 <= not Sig1;
        wait for 5 ns;
    end process;
 
    process(Sig1) is
    begin
        Sig2 <= Sig1;
    end process;
 
end architecture;