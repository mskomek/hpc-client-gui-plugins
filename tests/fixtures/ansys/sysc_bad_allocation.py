# System Coupling run script with invalid allocation
participantA = coupling.AddParticipant(ParticipantType="FLUENT")
participantB = coupling.AddParticipant(ParticipantType="MAPDL")
participantA.ParticipantFraction = 0.6
participantB.ParticipantFraction = 0.3
coupling.Initialize()
coupling.Solve()
