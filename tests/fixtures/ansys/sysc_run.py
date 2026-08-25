# System Coupling run script
participant = coupling.AddParticipant(
    ParticipantType="FLUENT",
    ParticipantPath="C:\\fluent\\case.cas.h5",
)
interface = coupling.AddInterface(
    SideOneParticipant=participant,
    SideTwoParticipant="MAPDL",
)
transfer = interface.AddDataTransfer()
coupling.Initialize()
coupling.Solve()
