// SPDX-License-Identifier: MIT
pragma solidity ^0.6.0;
contract Estimation {

  int  public mean;
  int  public threshold;
  uint public ticketPrice;
  int  public tau;
  bool public consensusReached;
  uint public startBlock;
  uint public valueUBI;
  uint public roundCount;
  uint public voteCount;
  uint public voteOkCount;
  uint public robotCount;
  uint public lastUpdate;
  bool public newRound;
  uint[10] blocksUBI; 
  int256 W_n;
  address payable [] public robotsToPay;

  struct voteInfo {
      address payable robotAddress;
      int256 vote;
    }
  
  struct robotInfo {
      address payable robotAddress;
      bool isRegistered;
      uint payout;
      uint lastUBI;
    }
   
  mapping(address => robotInfo) public robot;
  mapping(uint => voteInfo[]) public round;

  constructor() public {
      mean = 5000000;
      threshold = 2000000;
      ticketPrice = 40;
      tau = 100000;
      consensusReached = false;
      startBlock = block.number;
      valueUBI = 20;
      roundCount = 0;
      voteCount = 0;
      voteOkCount = 0;
      robotCount = 0;
      lastUpdate = 0;
      newRound = false;
      blocksUBI = [0,2,4,8,16,32,64,128,256,512];
      W_n = 0;
    }
  
  function abs(int x) internal pure returns (int y) {
    if (x < 0) {
      return -x;
    } 
    else {
      return x;
    }
  }
  
  function sqrt(int x) internal pure returns (int y) {
    int z = (x + 1) / 2;
    y = x;
    while (z < y) {
      y = z;
      z = (x / z + z) / 2;
    }
  }

  function isConverged() public view returns (bool) {
    return consensusReached;
  }
  function isNewRound() public view returns (bool) {
    return newRound;
  }
  function getMean() public view returns (int) {
    return mean;
  }
  function getVoteCount() public view returns (uint) {
    return voteCount;
  }
  function getVoteOkCount() public view returns (uint) {
    return voteOkCount;
  }
  function getRobotCount() public view returns (uint) { 
    return robotCount;
  }
  function getTicketPrice() public view returns (uint) { 
    return ticketPrice;
  }
  function sendFund() public payable {
  }

  function registerRobot() public {
    if (!robot[msg.sender].isRegistered) {
        robot[msg.sender].robotAddress = msg.sender;
        robot[msg.sender].isRegistered = true;
        robotCount += 1;
    }
  }
  
  function askForUBI() public returns (uint) {
    if (!robot[msg.sender].isRegistered) {
       return 0;
    }

    // Update the UBI due
    uint payoutUBI = 0;

    for (uint i = 0; i < blocksUBI.length; i++) {
      if (block.number-startBlock < blocksUBI[i]) {
      payoutUBI = (i - robot[msg.sender].lastUBI) * valueUBI;
      robot[msg.sender].lastUBI = i;
      break;
      }
    }

    // Transfer the UBI due
    if (payoutUBI > 0) {
      msg.sender.transfer(payoutUBI * 1 ether);
    }
    return payoutUBI;
  }
  
  function askForPayout() public returns (uint) {
    if (!robot[msg.sender].isRegistered) {
       return 0;
    }

    // Update the payout due
    uint payout = robot[msg.sender].payout;

    // Transfer the payout due
    msg.sender.transfer(payout * 1 ether);
    robot[msg.sender].payout = 0;
    return payout;
  }    
  
  function sendVote(int estimate) public payable {
    if (!robot[msg.sender].isRegistered || msg.value < ticketPrice * 1 ether) {
       revert();
    }
    
    voteCount += 1;

    round[roundCount].push(voteInfo(msg.sender, estimate));
    
    if (round[roundCount].length == robotCount) {
      roundCount += 1;
      newRound = true;
    }
  }
    
  function updateMean() public {  
    if (!robot[msg.sender].isRegistered || lastUpdate >= roundCount) {
       revert();
    }

    int oldMean = mean;  
    uint r = lastUpdate;

    // Check for OK Votes
    for (uint i = 0; i < round[r].length ; i++) {

      int256 delta = round[r][i].vote - mean;
  
      if (r == 0 || abs(delta) < threshold) {
        voteOkCount += 1;

        // Update mean
        int256 w_n = 1;
        W_n = W_n + w_n;
        mean += (w_n * delta) / W_n;

        // Record robots to be refunded
        robotsToPay.push(round[r][i].robotAddress);
      } 
    } 

    // Compute payouts
    for (uint b = 0; b < robotsToPay.length; b++) {
    robot[robotsToPay[b]].payout += ticketPrice * (round[r].length / robotsToPay.length);
    }

    // Determine consensus
    if ((abs(oldMean - mean) < tau) && voteOkCount > 2*robotCount) {
      consensusReached = true;
    }

    lastUpdate += 1;
    newRound = false;
    delete robotsToPay;
  }
}