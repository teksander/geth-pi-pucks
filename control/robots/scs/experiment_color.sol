// SPDX-License-Identifier: MIT
pragma solidity ^0.8.4;

contract ForagingPtManagement{
    uint constant num_pt = 100;
    uint constant max_life = 5;
    uint constant min_rep = 15; //Minimum number of reported points that make contract verified
    int256 constant radius = 10000;
    uint constant min_balance= 28000000000000000000; //Minimum number of balance to confirm a cluster


    address public minter;
    mapping (address => uint) public balances;

    struct Point{
        int x;
        int y;
        int z;
        uint credit; //deposited money in WEI
        uint category; //0:non useful, 1:useful
        int cluster;
        address sender;
        uint realType; //for experimental purpose only, the real food/non food type of the reported xy position
    }

    struct Cluster{
        int x;
        int y;
        int z;
        uint life;
        uint verified;
        uint num_rep; //Number of reported points that supports this cluster
        uint256 total_credit; //Sum of deposited credit
        uint256 total_credit_food; //Sum of deposited credit that report this point as food
        uint256 realType; //real food/non food type of the Initially reported Point of the cluster, for experimental purpose only
        address init_reporter;
    }

    struct clusterInfo{
        int x;
        int y;
        int z;
        int xo;
        int yo;
        int zo;
        int256 minDistance;
        uint minClusterIdx;
        uint foundCluster;
        uint minClusterStatus;
    }
    Point[] pointList;
    Cluster[] clusterList;
    clusterInfo info = clusterInfo(0,0,0,0,1e10,0,0,0);

    function getDistance(int256 _x1, int256 _x2, int256 _y1, int256 _y2, int256 _z1, int256 _z2) private pure returns(int256) {
        //5 digits floating num_pt
        return sqrt(((_x2 - _x1)**2) + ((_y2 - _y1)**2)+ ((_z2 - _z1)**2));
        //return abs(_x1-_x2)+abs(_y1-_y2);
    }

    function sqrt(int256 _kx) private pure returns (int256 _ky) {
      int256 _kz = (_kx + 1) / 2;
        _ky = _kx;
        while (_kz < _ky) {
            _ky = _kz;
            _kz = (_kx / _kz + _kz) / 2;
        }
      }
    function abs(int256 _k) private pure returns (int256) {
    return _k >= 0 ? _k : -_k;
    }



    function reportNewPt(int256 x, int256 y, int256 z, uint category, uint256 amount, uint256 realType) public payable{
        require(msg.value == amount);
        uint256 curtime = block.timestamp;
        // Assign point a cluster
        info.minDistance = 1e10;
        info.minClusterIdx = 0;
        info.foundCluster = 0;
        int256 x_avg = 0;
        int256 y_avg = 0;
        int256 z_avg = 0;
        int256 this_distance = 0;
        //recluster all points // can be skept in certain task configuration
        for (uint k=0; k<pointList.length; k++){
            for (uint i=0; i<clusterList.length; i++){
                //Process cluster expirationamount
                if (clusterList[i].verified==1 && clusterList[i].life<curtime){
                    // verified cluster where credit is already redistributed
                    clusterList[i].verified=2;
                }
                //Check if the newly reported pt belongs to any cluster
                if (clusterList[i].verified!=2){ //Not abandoned cluster
                    x_avg = (int256(clusterList[i].x)*int256(clusterList[i].total_credit)+ int256(pointList[k].x)*int256(amount))/int256(clusterList[i].total_credit+amount);
                    y_avg = (int256(clusterList[i].y)*int256(clusterList[i].total_credit)+ int256(pointList[k].y)*int256(amount))/int256(clusterList[i].total_credit+amount);
                    z_avg = (int256(clusterList[i].z)*int256(clusterList[i].total_credit)+ int256(pointList[k].z)*int256(amount))/int256(clusterList[i].total_credit+amount);

                    this_distance = getDistance(x_avg, pointList[k].x, y_avg,  pointList[k].y, pointList[k].z, z_avg);
                    if (this_distance<info.minDistance){
                        info.minDistance = this_distance;
                        info.minClusterIdx = i;
                        info.foundCluster = 1;
                        info.x=x_avg;
                        info.y=y_avg;
                        info.z=z_avg;
                        info.xo = x;
                        info.yo = y;
                        info.yo = z;
                        info.minClusterStatus = clusterList[i].verified;
                    }
                }
            }
            if (info.minClusterIdx != uint(pointList[k].cluster)){
                clusterList[uint(pointList[k].cluster)].num_rep-=1;
                clusterList[uint(pointList[k].cluster)].total_credit-=pointList[k].credit;
                if (pointList[k].category==1){
                    clusterList[uint(pointList[k].cluster)].total_credit_food-=pointList[k].credit;
                }
                clusterList[info.minClusterIdx].num_rep+=1;
                clusterList[info.minClusterIdx].total_credit+=pointList[k].credit;
                if (pointList[k].category==1){
                    clusterList[info.minClusterIdx].total_credit_food+=pointList[k].credit;
                }
                pointList[k].cluster = int256(info.minClusterIdx);
            }

        }

        //unique rep
        for (uint i=0; i<clusterList.length; i++){
            if (clusterList[i].verified==0){
                for (uint k=0; k<pointList.length-1; k++){
                    for (uint l=k+1; l<pointList.length; l++){
                        if (pointList[k].cluster == int256(i) && pointList[l].cluster == int256(i) && pointList[k].sender == pointList[l].sender){
                            payable(pointList[l].sender).transfer(pointList[l].credit);
                            clusterList[i].num_rep-=1;
                            clusterList[i].total_credit-=pointList[l].credit;
                            if (pointList[l].category==1){
                                clusterList[i].total_credit_food-=pointList[l].credit;
                            }
                            pointList[l].cluster=-1;
                         }
                    }
                }
            }

        }

        // Assign new point a cluster
        info.minDistance = 1e10;
        info.minClusterIdx = 0;
        info.foundCluster = 0;
        x_avg = 0;
        y_avg = 0;
        this_distance = 0;
        if (category==1 && clusterList.length == 0){
            clusterList.push(Cluster(x,y, curtime+max_life, 0, 1, amount, amount, realType, msg.sender));
            pointList.push(Point(x,y,amount, category, 0, msg.sender, realType));
        }
        else{
            // Search for closest unverified cluster
            for (uint i=0; i<clusterList.length; i++){
                //Process cluster expirationamount
                if (clusterList[i].verified==1 && clusterList[i].life<curtime){
                    // verified cluster where credit is already redistributed
                    clusterList[i].verified=2;
                }
                //Check if the newly reported pt belongs to any cluster
                if (clusterList[i].verified!=2){ //Not abandoned cluster
                    x_avg = (int256(clusterList[i].x)*int256(clusterList[i].total_credit)+ int256(x)*int256(amount))/int256(clusterList[i].total_credit+amount);
                    y_avg = (int256(clusterList[i].y)*int256(clusterList[i].total_credit)+ int256(y)*int256(amount))/int256(clusterList[i].total_credit+amount);
                    this_distance = getDistance(x_avg, x, y_avg,  y);
                    if (this_distance<=radius && this_distance<info.minDistance){
                        info.minDistance = this_distance;
                        info.minClusterIdx = i;
                        info.foundCluster = 1;
                        info.x=x_avg;
                        info.y=y_avg;
                        info.xo = x;
                        info.yo = y;
                        info.minClusterStatus = clusterList[i].verified;
                    }
                    else if (info.foundCluster == 0){
                        //only for debugging purpose
                        info.minDistance = this_distance;
                        info.minClusterIdx = i;
                        info.foundCluster = 0;
                        info.x=x_avg;
                        info.y=y_avg;
                        info.xo = x;
                        info.yo = y;
                        info.minClusterStatus = clusterList[i].verified;
                    }
                }
            }


            //if exists non-verified cluster that the new point belongs
            if (info.minClusterStatus == 0 && info.foundCluster==1 && clusterList[info.minClusterIdx].init_reporter != msg.sender){
                clusterList[info.minClusterIdx].num_rep+=1;
                clusterList[info.minClusterIdx].total_credit+=amount;
                //clusterList[info.minClusterIdx].total_uncertainty+=uncertainty;
                if (category==1){
                    clusterList[info.minClusterIdx].total_credit_food+=amount;
                }

                clusterList[info.minClusterIdx].x = info.x;
                clusterList[info.minClusterIdx].y = info.y;
                //ADD CORRESPONDING POINT
                pointList.push(Point(x,y,amount, category, int256(info.minClusterIdx), msg.sender, realType));
                //Remove redundant reporters from the pointList
                for (uint k=0; k<pointList.length-1; k++){
                    for (uint l=k+1; l<pointList.length; l++){
                        if (pointList[k].cluster == int256(info.minClusterIdx) && pointList[l].cluster == int256(info.minClusterIdx) && pointList[k].sender == pointList[l].sender){
                            payable(pointList[l].sender).transfer(pointList[l].credit);
                            clusterList[info.minClusterIdx].num_rep-=1;
                            clusterList[info.minClusterIdx].total_credit-=pointList[l].credit;
                            if (pointList[l].category==1){
                                clusterList[info.minClusterIdx].total_credit_food-=pointList[l].credit;
                            }
                            pointList[l].cluster=-1;
                         }
                    }
                }



                //If cluster receives enough samples, verified.
                uint256 total_non_food_credit = 0;
                uint256 bonus_credit = 0;
                if (clusterList[info.minClusterIdx].num_rep>=min_rep && clusterList[info.minClusterIdx].total_credit>=min_balance && clusterList[info.minClusterIdx].total_credit_food>(clusterList[info.minClusterIdx].total_credit-clusterList[info.minClusterIdx].total_credit_food)){
                    clusterList[info.minClusterIdx].verified=1; //cluster verified
                    clusterList[info.minClusterIdx].life = curtime+max_life;
                    total_non_food_credit = clusterList[info.minClusterIdx].total_credit-clusterList[info.minClusterIdx].total_credit_food;
                    //Redistribute money
                    uint256 food_num =0;
                    for (uint j=0; j<pointList.length; j++){
                        if (pointList[j].cluster == int256(info.minClusterIdx) && pointList[j].category ==1){
                            food_num+=1;
                         }
                    }

                    for (uint j=0; j<pointList.length; j++){
                        if (pointList[j].cluster == int256(info.minClusterIdx) && pointList[j].category ==1){
                            //bonus_credit = total_non_food_credit*pointList[j].credit/clusterList[info.minClusterIdx].total_credit_food;
                            if (food_num>0){
                                bonus_credit = total_non_food_credit/food_num;
                            }
                            else{
                                bonus_credit = 0;
                            }
                            payable(pointList[j].sender).transfer(bonus_credit+pointList[j].credit);
                         }
                    }
                    uint c = 0;
                    uint curLength = pointList.length;
                    while(c<curLength){
                        if (pointList[c].cluster == int256(info.minClusterIdx) || pointList[c].cluster==-1){
                            pointList[c] = pointList[pointList.length-1];
                            pointList.pop();
                            curLength = pointList.length;
                        }
                        else{
                            c+=1;
                        }
                    }
                }
                else if (clusterList[info.minClusterIdx].num_rep>=min_rep && clusterList[info.minClusterIdx].total_credit>=min_balance && clusterList[info.minClusterIdx].total_credit_food<(clusterList[info.minClusterIdx].total_credit-clusterList[info.minClusterIdx].total_credit_food)){
                    clusterList[info.minClusterIdx].verified=2; //cluster abandon
                    total_non_food_credit = clusterList[info.minClusterIdx].total_credit-clusterList[info.minClusterIdx].total_credit_food;
                    //Redistribute money
                    //WVG wining side
                    uint256 non_food_num =0;
                    for (uint j=0; j<pointList.length; j++){
                        if (pointList[j].cluster == int256(info.minClusterIdx) && pointList[j].category ==0){
                            non_food_num+=1;
                         }
                    }
                    for (uint j=0; j<pointList.length; j++){
                        if (pointList[j].cluster == int256(info.minClusterIdx) && pointList[j].category ==0){
                            // bonus_credit = clusterList[info.minClusterIdx].total_credit_food*pointList[j].credit/total_non_food_credit;
                            if (non_food_num>0){
                                bonus_credit = clusterList[info.minClusterIdx].total_credit_food/non_food_num;
                            }
                            else{
                                bonus_credit = 0;
                            }

                            payable(pointList[j].sender).transfer(bonus_credit+pointList[j].credit);
                         }
                    }
                    //remove points
                    uint c = 0;
                    uint curLength = pointList.length;
                    while(c<curLength){
                        if (pointList[c].cluster == int256(info.minClusterIdx) || pointList[c].cluster==-1){
                            pointList[c] = pointList[pointList.length-1];
                            pointList.pop();
                            curLength = pointList.length;
                        }
                        else{
                            c+=1;
                        }
                    }
                }
            }
            else if (category==1 && info.foundCluster==0 && clusterList[info.minClusterIdx].init_reporter != msg.sender){
                //if point reports a food source position and  belongs to nothing>inter cluster threshold, create new cluster, this is only for experimental purpose
                clusterList.push(Cluster(x,y,curtime + max_life, 0, 1, amount, amount, realType, msg.sender));
                pointList.push(Point(x,y,amount, category, int256(clusterList.length-1), msg.sender, realType));
            }
            else{
                //Do nothing and transfer back, if anything else
                payable(msg.sender).transfer(amount);
            }
        }
    }

    function getSourceList() public view returns(Cluster[] memory){
        return clusterList;
    }

    function getClusterInfo() public view returns(clusterInfo memory){
        return info;
    }
    function getPointListInfo() public view returns(Point[]  memory){
        return pointList;
    }
}