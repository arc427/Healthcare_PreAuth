const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("PriorAuthorization Smart Contract", function () {
  let contract;
  let owner;
  let hospital;
  let otherAccount;

  beforeEach(async function () {
    [owner, hospital, otherAccount] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("PriorAuthorization");
    contract = await Factory.deploy();
    await contract.waitForDeployment();
  });

  describe("Deployment", function () {
    it("Sets the deploying account as owner", async function () {
      expect(await contract.owner()).to.equal(owner.address);
    });

    it("Starts with 0 initial requests", async function () {
      expect(await contract.requestCount()).to.equal(0);
    });
  });

  describe("submitRequest", function () {
    it("Allows any hospital address to submit a request and emits event", async function () {
      const docHash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";
      
      await expect(contract.connect(hospital).submitRequest(docHash))
        .to.emit(contract, "RequestCreated");

      expect(await contract.requestCount()).to.equal(1);

      const req = await contract.getRequest(1);
      expect(req.id).to.equal(1);
      expect(req.documentHash).to.equal(docHash);
      expect(req.hospital).to.equal(hospital.address);
      expect(req.status).to.equal(0); // Status.Pending
    });

    it("Rejects submitting request with empty documentHash", async function () {
      await expect(contract.connect(hospital).submitRequest("")).to.be.revertedWith(
        "Document hash is required"
      );
    });
  });

  describe("evaluateRequest", function () {
    const docHash = "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e";

    beforeEach(async function () {
      await contract.connect(hospital).submitRequest(docHash);
    });

    it("Allows owner (insurer) to approve a pending request", async function () {
      await expect(contract.connect(owner).evaluateRequest(1, 1)) // Status.Approved
        .to.emit(contract, "RequestEvaluated")
        .withArgs(1, 1, owner.address);

      const req = await contract.getRequest(1);
      expect(req.status).to.equal(1); // Approved
    });

    it("Allows owner (insurer) to reject a pending request", async function () {
      await contract.connect(owner).evaluateRequest(1, 2); // Status.Rejected
      const req = await contract.getRequest(1);
      expect(req.status).to.equal(2); // Rejected
    });

    it("Prevents non-owner from evaluating a request", async function () {
      await expect(contract.connect(otherAccount).evaluateRequest(1, 1)).to.be.revertedWith(
        "Only the insurer/owner can evaluate requests"
      );
    });

    it("Prevents evaluating an already evaluated request", async function () {
      await contract.connect(owner).evaluateRequest(1, 1);
      await expect(contract.connect(owner).evaluateRequest(1, 1)).to.be.revertedWith(
        "Request already evaluated"
      );
    });

    it("Rejects invalid request IDs", async function () {
      await expect(contract.connect(owner).evaluateRequest(999, 1)).to.be.revertedWith(
        "Invalid request id"
      );
    });

    it("Rejects evaluation with Pending status", async function () {
      await expect(contract.connect(owner).evaluateRequest(1, 0)).to.be.revertedWith(
        "Status must be Approved or Rejected"
      );
    });
  });
});
