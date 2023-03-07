// SPDX-License-Identifier: MIT
pragma solidity >=0.4.0 <0.7.0;

contract Greeter {
    uint public greeting;

    struct voteInfo {
      address payable robotAddress;
      uint estimate;
    }

    voteInfo[] voteList;

    function Greeters() public {
        greeting = 0;
    }

    function setGreeting(uint _greeting) public {
        greeting += _greeting;
        voteInfo memory vi = voteInfo(msg.sender, _greeting);
        voteList.push(vi);
        if (voteList.length == 4) {
             greeting = 0;
        }
    }

    function greet() view public returns (uint) {
    return greeting;
    }
}