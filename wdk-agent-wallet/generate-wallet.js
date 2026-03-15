import WDK from '@tetherto/wdk'
import WalletManagerEvm from '@tetherto/wdk-wallet-evm'

async function main() {
  console.log('=== WDK Agent Wallet Generator ===\n')

  try {
    // Generate a fresh seed phrase for the agent wallet
    const seedPhrase = WDK.getRandomSeedPhrase()
    console.log('Generated Seed Phrase (SAVE THIS SECURELY):')
    console.log(seedPhrase)
    console.log()

    // Register only the EVM (Ethereum) wallet using Sepolia testnet
    const wdkWithWallets = new WDK(seedPhrase)
      .registerWallet('ethereum', WalletManagerEvm, {
        provider: 'https://sepolia.drpc.org'
      })

    // Get the first account (index 0)
    const ethAccount = await wdkWithWallets.getAccount('ethereum', 0)
    const address = await ethAccount.getAddress()

    console.log('Agent Ethereum Address:', address)
    console.log()
    console.log('=== Copy the address above into your .env as needed ===')
    console.log('=== Store the seed phrase securely — you need it to recover the wallet ===')

    process.exit(0)
  } catch (error) {
    console.error('Error:', error.message)
    process.exit(1)
  }
}

main()
