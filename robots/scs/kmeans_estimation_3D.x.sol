// SPDX-License-Identifier: MIT
pragma solidity ^0.8.4;

contract ForagingPtManagement{

    uint constant space_size  = DIMS;
    uint constant num_pt      = NUMPT;
    uint constant max_life    = MAXLIFE;
    uint constant min_rep     = MINREP;     //Minimum number of reported points that make contract verified
    int256 constant radius    = RADIUS;
    uint constant min_balance = MINBALANCE; //Minimum number of balance to confirm a cluster
    int256 constant max_unverified_cluster =  MAXUNVCLUSTER;


    address public minter;
    mapping (address => uint) public balances;

    struct Point{
        // int x;
        // int y;
        int[space_size] position;
        uint credit;   // deposited money in WEI
        uint category; // 0:non-food, 1:food
        int cluster;
        address sender;
        uint realType; // for debugging: the real category of the reported point
    }

    struct Cluster{
        // int x;
        // int y;
        int[space_size] position;
        uint life;
        uint verified;
        uint num_rep; //Number of reported points that supports this cluster
        uint256 total_credit; //Sum of deposited credit
        uint256 total_credit_food; //Sum of deposited credit that report this point as food
        uint256 realType; //real food/non food type of the Initially reported Point of the cluster, for experimental purpose only
        address init_reporter;
        uint256 intention; //intention = 0 initial report, intention = 1 verification, avoid verification req to be listed as init report
        int[space_size] sup_position;
    }

    struct clusterInfo{
        // int x;
        // int y;
        // int xo;
        // int yo;
        int[space_size] position;
        int[space_size] positiono;
        int256 minDistance;
        uint minClusterIdx;
        uint foundCluster;
        uint minClusterStatus;
    }

    int[space_size] position_zeros;
    Point[] pointList;
    Cluster[] clusterList;
    clusterInfo info = clusterInfo(position_zeros,position_zeros,1e10,0,0,0);
    int256 unverfied_clusters = 0;

    // function reportNewPt(int256 x, int256 y, uint category, uint256 amount, uint256 realType, uint256 intention) public payable{
    function reportNewPt(int256[space_size] memory position, uint category, uint256 amount, uint256 realType, uint256 intention) public payable{
        require(msg.value == amount);
        uint256 curtime = block.timestamp;
    }

    //----- setters and getters ------

    function getSourceList() public view returns(int){
        return 0;
    }
    function getClusterInfo() public view returns(int){
        return 0;
    }
    function getPointListInfo() public view returns(int){
        return 0;
    }

}