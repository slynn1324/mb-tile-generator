
/* [Hidden] */
large_octagon_hole_with_side_holes_file = "remix-files/Large Octagon Hole with side holes (Positive).stl";
small_thread_hole_with_side_bumps_file = "remix-files/Small Thread Hole with side bumps (Positive).stl";


spacing = 25;

// CORNER_STYLES
NONE = "none";
SMALL_THREAD = "small_thread";
EDGE_V = "edge_v";
EDGE_H = "edge_h";

// CELL_STYLES
SKIP = "skip";
NORMAL = [ SMALL_THREAD, NONE, NONE, NONE ];
BOTTOM_LEFT_CORNER = [ SMALL_THREAD, EDGE_H, NONE, EDGE_V ];
TOP_LEFT_CORNER = [EDGE_H, NONE, NONE, NONE ];
TOP_RIGHT_CORNER = [NONE, NONE, NONE, NONE ];
BOTTOM_RIGHT_CORNER = [EDGE_V, NONE, NONE, NONE ];
LEFT_EDGE = [ SMALL_THREAD, NONE, NONE, EDGE_V ];
RIGHT_EDGE = [ EDGE_V, NONE, NONE, NONE ];
BOTTOM_EDGE = [ SMALL_THREAD, EDGE_H, NONE, NONE ];
TOP_EDGE = [ EDGE_H, NONE, NONE, NONE ];





LAYOUT = [
    [ NORMAL, NORMAL, NORMAL, RIGHT_EDGE ],
    [ NORMAL, NORMAL, NORMAL, RIGHT_EDGE ],
    [ NORMAL, NORMAL, NORMAL, RIGHT_EDGE ],
    [ NORMAL, NORMAL, NORMAL, RIGHT_EDGE ],
    [ NORMAL, NORMAL, NORMAL, RIGHT_EDGE ],
    [ NORMAL, NORMAL, NORMAL, RIGHT_EDGE ],
    [ NORMAL, NORMAL, NORMAL, RIGHT_EDGE ],
    [ NORMAL, NORMAL, NORMAL, RIGHT_EDGE ],
    [ BOTTOM_EDGE, BOTTOM_EDGE, BOTTOM_EDGE, BOTTOM_RIGHT_CORNER ]
];

// LAYOUT = [
//     [ [NONE, SMALL_THREAD, NONE, SMALL_THREAD], NORMAL ]
// ];




// the grid is flipped from layout in the y direction, so we build bottom-up
grid = [for (i = [len(LAYOUT)-1 : -1 : 0]) LAYOUT[i]];

module small_thread(){
    import(small_thread_hole_with_side_bumps_file);
}

module gap_filler(){
    translate([12.5, 12.5, 0]){
        rotate([0,0,-45]){
            translate([-1*10.355/2, -1*10.355/2,0]){
                translate([(10.355-8)/2,-1,(6.2-4)/2]){
                    cube([8,1,4]);
                }
            }
        }
    }
}

module filler_with_side_bumps(){
    small_thread();
    translate([12.5, 12.5, 0]){
        rotate([0,0,-45]){
            translate([-1*10.355/2, -1*10.355/2,0]){
                cube([10.355,10.355,6.2]);
            }
        }
    }
}

module vertical_edge_with_side_bumps(){
    intersection(){
        filler_with_side_bumps();

        cube([12.5,50,10]);
    }
}

module horizontal_edge_with_side_bumps(){
    intersection(){
        filler_with_side_bumps();
        cube([50,12.5,10]);
    }
}

for ( y = [0:len(grid)-1]){
    translate([0, y*spacing, 0]) {
    
        for ( x = [0:len(grid[y])-1]){
  
            if ( grid[y][x] != SKIP ){

                translate([x*spacing, 0, 0]){
                
            
                    import(large_octagon_hole_with_side_holes_file);
                    
                    // echo("y=", y, " x=", x, " setting=", grid[y][x]);
                    
                    // top right corner
                    if ( grid[y][x][0] == EDGE_V ){
                        vertical_edge_with_side_bumps();
                        gap_filler();
                    }

                    if ( grid[y][x][0] == EDGE_H ){
                        horizontal_edge_with_side_bumps();
                        gap_filler();
                    }

                    if ( grid[y][x][0] == SMALL_THREAD ){
                        small_thread();
                        gap_filler();
                    }

                    // bottom right corner
                    if ( grid[y][x][1] == EDGE_V ){
                        mirror([0,1,0]){
                            vertical_edge_with_side_bumps();
                            gap_filler();
                        }
                    }

                    if ( grid[y][x][1] == EDGE_H ){
                        mirror([0,1,0]){
                            horizontal_edge_with_side_bumps();
                            gap_filler();
                        }
                    }

                    if ( grid[y][x][1] == SMALL_THREAD ){
                        mirror([0,1,0]){
                            small_thread();
                            gap_filler();
                        }
                    }

                    // bottom left corner
                    if ( grid[y][x][2] == EDGE_V ){
                        mirror([1,0,0]){
                            mirror([0,1,0]){
                                vertical_edge_with_side_bumps();
                                gap_filler();
                            }
                        }
                    }

                    if ( grid[y][x][2] == EDGE_H ){
                        mirror([1,0,0]){
                            mirror([0,1,0]){
                                horizontal_edge_with_side_bumps();
                                gap_filler();
                            }
                        }
                    }

                    if ( grid[y][x][2] == SMALL_THREAD ){
                        mirror([1,0,0]){
                            mirror([0,1,0]){
                                small_thread();
                                gap_filler();
                            }
                        }
                    }

                    // top left corner
                    if ( grid[y][x][3] == EDGE_V ){
                        mirror([1,0,0]){
                            vertical_edge_with_side_bumps();
                            gap_filler();
                        }
                    }

                    if ( grid[y][x][3] == EDGE_H ){
                        mirror([1,0,0]){
                            horizontal_edge_with_side_bumps();
                            gap_filler();
                        }
                    }

                    if ( grid[y][x][3] == SMALL_THREAD ){
                        mirror([1,0,0]){
                            small_thread();
                            gap_filler();
                        }
                    }
                    
                    
                    // fix gaps
                    // fix gaps -- bottom-right
                    if ( y-1 >= 0 && grid[y-1][x][0] != NONE ){
                         mirror([0,1,0]){
                            gap_filler();
                        }
                    }

                    // fix gaps -- bottom-left
                    if ( x-1 >= 0 && y-1 >= 0 && grid[y-1][x-1][0] != NONE ){
                        mirror([1,0,0]){
                            mirror([0,1,0]){
                                gap_filler();
                            }
                        }
                    }

                    // fix gaps -- top-left
                    if ( x-1 >= 0 && grid[y][x-1][0] != NONE ){
                        mirror([1,0,0]){
                            gap_filler();
                        }
                    }

                    // fix gaps -- cell to left 
                    if ( x-1 >= 0 && grid[y][x-1][1] != NONE ){
                        mirror([1,0,0]){
                            mirror([0,1,0]){
                                gap_filler();
                            }
                        }
                    }

                    // fix gaps -- cell below 
                    if ( y-1 >= 0 && grid[y-1][x][3] != NONE ){
                        mirror([1,0,0]){
                            mirror([0,1,0]){
                                gap_filler();
                            }
                        }
                    }
                    
                } // end translate

            } // end skip

        }
    }
}