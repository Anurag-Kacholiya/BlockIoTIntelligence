// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title IoTRegistry — identity, integrity, provenance and audit ledger for BlockIoTIntelligence (ADR §6).
/// @notice Only hashes and small metadata go on-chain; raw telemetry, features and model weights stay off-chain.
///         Device signatures are Ed25519 and are verified off-chain by the edge against `pubKeyHash`.
contract IoTRegistry {
    // Layer ids match src/common/schemas.py:Layer.
    uint8 constant DEVICE = 0;
    uint8 constant EDGE = 1;
    uint8 constant FOG = 2;
    uint8 constant CLOUD = 3;

    struct Device {
        bytes32 pubKeyHash;
        uint64 registeredAt;
        bool active;
    }

    struct Commitment {
        bytes32 deviceId;
        bytes32 payloadHash;   // sha256 of the canonical event (per-event mode) or Merkle root (batch mode)
        uint64 timestamp;
        uint32 count;          // 1 for a single event, n for a batch
        uint8 layer;
    }

    struct Model {
        bytes32 modelHash;
        uint64 registeredAt;
        uint8 layer;
        string metadataUri;
    }

    address public immutable owner;
    mapping(address => bool) public authorized;          // edge / fog / cloud node accounts and device gateways
    mapping(bytes32 => Device) public devices;
    mapping(bytes32 => Commitment) public commitments;   // eventId or batchId => commitment
    mapping(bytes32 => bytes32) public processed;        // eventId or batchId => processed hash (edge)
    mapping(bytes32 => bytes32) public alerts;           // alertId => alert hash (fog)
    mapping(bytes32 => Model) public models;             // modelId => model record (cloud)

    event DeviceRegistered(bytes32 indexed deviceId, bytes32 pubKeyHash, string metadataUri);
    event DeviceRevoked(bytes32 indexed deviceId);
    event DataCommitted(bytes32 indexed id, bytes32 indexed deviceId, bytes32 payloadHash, uint32 count, uint8 layer);
    event ProcessingRecorded(bytes32 indexed id, bytes32 parentHash, bytes32 processedHash, uint8 layer);
    event AlertRecorded(bytes32 indexed alertId, bytes32 alertHash, bytes32 indexed fogId, uint64 timestamp);
    event ModelRegistered(bytes32 indexed modelId, bytes32 modelHash, uint8 layer, string metadataUri);
    event InferenceRecorded(bytes32 indexed batchId, bytes32 indexed modelId, bytes32 resultHash, uint64 timestamp);

    error NotOwner();
    error NotAuthorized();
    error UnknownDevice();
    error AlreadyCommitted();
    error AlreadyProcessed();
    error NotCommitted();

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    modifier onlyAuthorized() {
        if (!authorized[msg.sender] && msg.sender != owner) revert NotAuthorized();
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    // ---- identity -------------------------------------------------------------------------------

    function authorize(address node, bool allowed) external onlyOwner {
        authorized[node] = allowed;
    }

    function registerDevice(bytes32 deviceId, bytes32 pubKeyHash, string calldata metadataUri) external onlyOwner {
        devices[deviceId] = Device(pubKeyHash, uint64(block.timestamp), true);
        emit DeviceRegistered(deviceId, pubKeyHash, metadataUri);
    }

    function revokeDevice(bytes32 deviceId) external onlyOwner {
        devices[deviceId].active = false;
        emit DeviceRevoked(deviceId);
    }

    // ---- device: data commitments ---------------------------------------------------------------

    /// Per-event commitment. An eventId can be committed once, which blocks on-chain replays.
    function commitData(bytes32 eventId, bytes32 deviceId, bytes32 payloadHash, uint8 layer, uint64 timestamp)
        external
        onlyAuthorized
    {
        if (!devices[deviceId].active) revert UnknownDevice();
        if (commitments[eventId].timestamp != 0) revert AlreadyCommitted();
        commitments[eventId] = Commitment(deviceId, payloadHash, timestamp, 1, layer);
        emit DataCommitted(eventId, deviceId, payloadHash, 1, layer);
    }

    /// Batch commitment: one Merkle root over `count` event hashes from one device (ADR §13.1 D aggregation).
    function commitBatch(bytes32 batchId, bytes32 deviceId, bytes32 merkleRoot, uint32 count, uint64 timestamp)
        external
        onlyAuthorized
    {
        if (!devices[deviceId].active) revert UnknownDevice();
        if (commitments[batchId].timestamp != 0) revert AlreadyCommitted();
        commitments[batchId] = Commitment(deviceId, merkleRoot, timestamp, count, DEVICE);
        emit DataCommitted(batchId, deviceId, merkleRoot, count, DEVICE);
    }

    // ---- edge: processing provenance ------------------------------------------------------------

    function recordProcessing(bytes32 id, bytes32 parentHash, bytes32 processedHash, uint8 layer)
        external
        onlyAuthorized
    {
        if (commitments[id].timestamp == 0) revert NotCommitted();
        if (processed[id] != bytes32(0)) revert AlreadyProcessed();
        processed[id] = processedHash;
        emit ProcessingRecorded(id, parentHash, processedHash, layer);
    }

    // ---- fog: alert audit -----------------------------------------------------------------------

    function recordAlert(bytes32 alertId, bytes32 alertHash, bytes32 fogId, uint64 timestamp) external onlyAuthorized {
        alerts[alertId] = alertHash;
        emit AlertRecorded(alertId, alertHash, fogId, timestamp);
    }

    /// Many alerts in one transaction; each is still individually auditable through its event log.
    function recordAlerts(bytes32[] calldata alertIds, bytes32[] calldata alertHashes, bytes32 fogId, uint64 timestamp)
        external
        onlyAuthorized
    {
        for (uint256 i = 0; i < alertIds.length; i++) {
            alerts[alertIds[i]] = alertHashes[i];
            emit AlertRecorded(alertIds[i], alertHashes[i], fogId, timestamp);
        }
    }

    // ---- cloud: model provenance ----------------------------------------------------------------

    function registerModel(bytes32 modelId, bytes32 modelHash, uint8 layer, string calldata metadataUri)
        external
        onlyAuthorized
    {
        models[modelId] = Model(modelHash, uint64(block.timestamp), layer, metadataUri);
        emit ModelRegistered(modelId, modelHash, layer, metadataUri);
    }

    function recordInference(bytes32 batchId, bytes32 modelId, bytes32 resultHash, uint64 timestamp)
        external
        onlyAuthorized
    {
        emit InferenceRecorded(batchId, modelId, resultHash, timestamp);
    }
}
