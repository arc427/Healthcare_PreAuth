// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract PriorAuthorization {
    enum Status {
        Pending,
        Approved,
        Rejected
    }

    struct Request {
        uint id;
        string documentHash;
        address hospital;
        Status status;
        uint256 timestamp;
    }

    address public owner;
    uint public requestCount;
    mapping(uint => Request) public requests;

    event RequestCreated(
        uint indexed id,
        string documentHash,
        address indexed hospital,
        uint256 timestamp
    );

    event RequestEvaluated(
        uint indexed id,
        Status status,
        address indexed evaluator
    );

    modifier onlyOwner() {
        require(msg.sender == owner, "Only the insurer/owner can evaluate requests");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    function submitRequest(string memory documentHash) public returns (uint) {
        require(bytes(documentHash).length > 0, "Document hash is required");

        requestCount += 1;
        uint newId = requestCount;

        requests[newId] = Request({
            id: newId,
            documentHash: documentHash,
            hospital: msg.sender,
            status: Status.Pending,
            timestamp: block.timestamp
        });

        emit RequestCreated(newId, documentHash, msg.sender, block.timestamp);
        return newId;
    }

    function evaluateRequest(uint requestId, Status newStatus) public onlyOwner {
        require(requestId > 0 && requestId <= requestCount, "Invalid request id");
        require(newStatus == Status.Approved || newStatus == Status.Rejected, "Status must be Approved or Rejected");

        Request storage existing = requests[requestId];
        require(existing.status == Status.Pending, "Request already evaluated");

        existing.status = newStatus;
        emit RequestEvaluated(requestId, newStatus, msg.sender);
    }

    function getRequest(uint requestId) public view returns (Request memory) {
        require(requestId > 0 && requestId <= requestCount, "Invalid request id");
        return requests[requestId];
    }
}
