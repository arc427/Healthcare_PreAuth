const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying PriorAuthorization with insurer/owner:", deployer.address);

  const Factory = await hre.ethers.getContractFactory("PriorAuthorization");
  const contract = await Factory.deploy();
  await contract.waitForDeployment();

  const address = await contract.getAddress();
  const artifact = await hre.artifacts.readArtifact("PriorAuthorization");
  const network = await hre.ethers.provider.getNetwork();

  const payload = {
    address,
    abi: artifact.abi,
    chainId: Number(network.chainId),
    owner: deployer.address,
    rpcUrl: "http://127.0.0.1:8545",
  };

  const root = path.join(__dirname, "..");
  const appPath = path.join(root, "app", "contract.json");
  const publicPath = path.join(root, "public", "contract.json");

  fs.writeFileSync(appPath, JSON.stringify(payload, null, 2));
  fs.writeFileSync(publicPath, JSON.stringify(payload, null, 2));

  console.log("PriorAuthorization deployed to:", address);
  console.log("Wrote contract metadata to:");
  console.log(" -", appPath);
  console.log(" -", publicPath);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
