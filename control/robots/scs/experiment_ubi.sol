// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;
contract Estimation {

int  public mean;
int  public count;
int  public threshold;
int  public roundthreshold;
int  public m2;
uint public ticketPrice;
int  public round;
int  public numCurrentVotes;
uint  public NEEDEDVOTES;
uint public localCount;
uint public weightCount;
uint public voteCount;
uint public outliers;
int  public tau;
uint public consensusReached;
uint public startBlock;
uint public valueUBI;
int256 W_n;

struct votingInformation {
    address payable robot;
    int256 quality;
    uint blockNumber;
    int weight;
    uint money;
    int diff;
  }

uint[10] blocksUBI; 
votingInformation[] allVotes;
address payable [] public robotsToPay;


mapping(address => uint) public receivedUBI;
mapping(address => int) public payoutForAddress;
mapping(address => int256) public weights;

constructor() {
    mean = 5000000;
    count = 0;
    roundthreshold = 2000000;
    ticketPrice = 40;
    numCurrentVotes = 0;
    NEEDEDVOTES = 20;
    localCount = 0;
    weightCount = 0;
    voteCount = 0;
    outliers = 6;
    tau = 200000;
    consensusReached = 0;
    W_n = 0;
    valueUBI = 20;
    blocksUBI = [0,2,4,8,16,32,64,128,256,521];
  }

function abs(int x) internal pure returns (int y) {
    if (x < 0) {
      return -x;
    } else {
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

function getBalance() public view returns (uint) {
    return address(this).balance;
  }
function getBlockNumber() public view returns (uint) {
    return block.number;
  }
function getMean() public view returns (int) {
    return mean;
  }
function getCount() public view returns (int) {
    return count;
  }
function getWeight() public view returns (int256) {
    return weights[msg.sender];
  }
function getSenderBalance() public view returns (uint) {
    return msg.sender.balance;
  }

function setRobotCount(uint _nRobots) public {
    NEEDEDVOTES = _nRobots;
}

function setStartBlock(uint _sBlock) public {
    startBlock = _sBlock;
}

function askForUBI() public {
  uint expectedUBI;
  for (uint i = 0; i < blocksUBI.length; i++) {
      if (block.number-startBlock < blocksUBI[i]) {
      expectedUBI = i;
      break;
      }
  }

  payable(msg.sender).transfer((expectedUBI - receivedUBI[msg.sender]) * valueUBI * 1 ether);
  receivedUBI[msg.sender] = expectedUBI;
}

function storeEth() public payable {

}

function askForPayout() public {
  if (allVotes.length > NEEDEDVOTES) {

    address payable r;

    int oldMean = mean;    

    for (uint a = 0; a < allVotes.length; a++) {                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 

      int256 delta = allVotes[a].quality - mean;

      if (round == 0 || abs(delta) < roundthreshold) {

    weightCount = weightCount + 1;

        // Get sender of that message
        r = allVotes[a].robot;

    robotsToPay.push(r);

        localCount = localCount + 1;

    int256 w_n = 1;
    W_n = W_n + w_n;
    mean += (w_n * delta) / W_n;
    count = count + 1;

      }
  }

    // Reimburse robots
    uint payoutFactor = allVotes.length / robotsToPay.length;
    for (uint b = 0; b < robotsToPay.length; b++) {
      robotsToPay[b].transfer((ticketPrice - 1) * 1 ether * payoutFactor);
    }

    round = round + 1;
    delete allVotes;
    delete robotsToPay;

    // Determine consensus
    if (consensusReached == 2 || ((abs(oldMean - mean) < tau) && localCount > 2*NEEDEDVOTES)) {
      consensusReached = 2;
    } else {
      consensusReached = 1;
    }
  }    
}

function vote(int x_n) public payable {
  if (msg.value < ticketPrice * 1 ether) {
     revert();
  }
  int weight = int(msg.sender.balance);
  voteCount += 1;
  votingInformation memory vi = votingInformation(payable(msg.sender), x_n, block.number, weight, msg.value, 0);
  allVotes.push(vi);
  askForPayout();
  }

}