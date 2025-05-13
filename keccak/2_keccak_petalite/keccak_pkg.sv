package keccak_pkg;

  // Constants
  parameter int num_plane = 5;
  parameter int num_sheet = 5;
  parameter int w = 64;
  parameter int rate = 1088;
  parameter int capacity = 1600 - rate;

  // Types
  typedef logic [w-1:0] k_lane;
  typedef k_lane k_plane [num_sheet];
  typedef k_plane k_state [num_plane];

endpackage