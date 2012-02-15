<?xml version="1.0" encoding="UTF-8"?>
<structure version="9" htmlmode="strict" relativeto="*SPS" encodinghtml="UTF-8" encodingrtf="ISO-8859-1" encodingpdf="UTF-8" useimportschema="1" embed-images="1">
	<parameters/>
	<schemasources>
		<namespaces>
			<nspair prefix="sb" uri="skylinebill"/>
			<nspair prefix="ub" uri="utilitybill"/>
		</namespaces>
		<schemasources>
			<xsdschemasource name="XML" main="1" schemafile="C:\workspace-skyline\billing\UtilityBill.xsd" workingxmlfile="C:\workspace-skyline\billing\sample\Pepco-3091-4490-03-20080908.xml">
				<xmltablesupport/>
				<textstateicons/>
			</xsdschemasource>
		</schemasources>
	</schemasources>
	<modules/>
	<flags>
		<scripts/>
		<globalparts/>
		<designfragments/>
		<pagelayouts/>
	</flags>
	<scripts>
		<script language="javascript"/>
	</scripts>
	<importedxslt/>
	<globalstyles/>
	<mainparts>
		<children>
			<globaltemplate subtype="main" match="/">
				<children>
					<documentsection>
						<properties columncount="1" columngap="0.50in" headerfooterheight="fixed" pagemultiplepages="0" pagenumberingformat="1" pagenumberingstartat="auto" pagestart="next" paperheight="11in" papermarginbottom="0.79in" papermarginfooter="0.30in" papermarginheader="0.30in" papermarginleft="0.60in" papermarginright="0.60in" papermargintop="0.79in" paperwidth="8.50in"/>
					</documentsection>
					<template subtype="source" match="XML">
						<children>
							<condition>
								<children>
									<conditionbranch xpath="child::ub:utilitybill/ub:measuredusage">
										<children>
											<paragraph>
												<children>
													<paragraph paragraphtag="h2">
														<children>
															<text fixtext="Skyline Measured Usage"/>
														</children>
													</paragraph>
													<template subtype="element" match="ub:utilitybill">
														<children>
															<template subtype="element" match="ub:measuredusage">
																<children>
																	<template subtype="element" match="ub:meter">
																		<children>
																			<template subtype="element" groupingtype="group-by" groupingmatch="ub:identifier" match="ub:register">
																				<sort>
																					<key match="current-grouping-key()"/>
																				</sort>
																				<children>
																					<tgrid>
																						<properties border="1"/>
																						<children>
																							<tgridbody-cols>
																								<children>
																									<tgridcol/>
																									<tgridcol/>
																									<tgridcol/>
																								</children>
																							</tgridbody-cols>
																							<tgridheader-rows>
																								<children>
																									<tgridrow>
																										<children>
																											<tgridcell/>
																											<tgridcell/>
																											<tgridcell/>
																										</children>
																									</tgridrow>
																								</children>
																							</tgridheader-rows>
																							<tgridbody-rows>
																								<children>
																									<template subtype="userdefined" match="current-group()">
																										<children>
																											<tgridrow>
																												<children>
																													<tgridcell>
																														<children>
																															<template subtype="attribute" match="shadow">
																																<children>
																																	<content/>
																																</children>
																																<variables/>
																															</template>
																														</children>
																													</tgridcell>
																													<tgridcell>
																														<children>
																															<template subtype="element" match="ub:identifier">
																																<children>
																																	<content/>
																																</children>
																																<variables/>
																															</template>
																														</children>
																													</tgridcell>
																													<tgridcell>
																														<children>
																															<template subtype="element" match="ub:total">
																																<children>
																																	<content>
																																		<format datatype="decimal"/>
																																	</content>
																																</children>
																																<variables/>
																															</template>
																														</children>
																													</tgridcell>
																												</children>
																											</tgridrow>
																										</children>
																										<variables/>
																									</template>
																								</children>
																							</tgridbody-rows>
																						</children>
																					</tgrid>
																					<text fixtext="   "/>
																				</children>
																				<variables/>
																			</template>
																		</children>
																		<variables/>
																	</template>
																</children>
																<variables/>
															</template>
														</children>
														<variables/>
													</template>
												</children>
											</paragraph>
											<line/>
										</children>
									</conditionbranch>
								</children>
							</condition>
							<newline/>
							<newline/>
							<newline/>
							<paragraph>
								<children>
									<paragraph paragraphtag="h2">
										<children>
											<text fixtext="Billable Usage"/>
										</children>
									</paragraph>
									<tgrid>
										<properties align="right" border="0" width="100%"/>
										<children>
											<tgridbody-cols>
												<children>
													<tgridcol/>
													<tgridcol/>
													<tgridcol/>
													<tgridcol/>
												</children>
											</tgridbody-cols>
											<tgridheader-rows>
												<children>
													<tgridrow>
														<children>
															<tgridcell>
																<properties align="left"/>
																<children>
																	<paragraph paragraphtag="h3">
																		<children>
																			<text fixtext="Service"/>
																		</children>
																	</paragraph>
																</children>
															</tgridcell>
															<tgridcell>
																<properties align="left"/>
																<children>
																	<paragraph paragraphtag="h3">
																		<children>
																			<text fixtext="Rate Schedule"/>
																		</children>
																	</paragraph>
																</children>
															</tgridcell>
															<tgridcell>
																<children>
																	<tgrid>
																		<properties align="left" border="0" width="100%"/>
																		<children>
																			<tgridbody-cols>
																				<children>
																					<tgridcol/>
																					<tgridcol/>
																					<tgridcol/>
																				</children>
																			</tgridbody-cols>
																			<tgridbody-rows>
																				<children>
																					<tgridrow>
																						<children>
																							<tgridcell>
																								<properties align="left"/>
																								<children>
																									<paragraph paragraphtag="h3">
																										<children>
																											<text fixtext="Description"/>
																										</children>
																									</paragraph>
																								</children>
																							</tgridcell>
																							<tgridcell>
																								<properties align="left"/>
																								<children>
																									<paragraph paragraphtag="h3">
																										<children>
																											<text fixtext="Quantity"/>
																										</children>
																									</paragraph>
																								</children>
																							</tgridcell>
																							<tgridcell/>
																						</children>
																					</tgridrow>
																				</children>
																			</tgridbody-rows>
																		</children>
																	</tgrid>
																</children>
															</tgridcell>
															<tgridcell>
																<properties align="right"/>
																<children>
																	<paragraph paragraphtag="h3">
																		<children>
																			<text fixtext="Total"/>
																		</children>
																	</paragraph>
																</children>
															</tgridcell>
														</children>
													</tgridrow>
												</children>
											</tgridheader-rows>
											<tgridbody-rows>
												<children>
													<template subtype="element" match="ub:utilitybill">
														<children>
															<template subtype="element" match="ub:billableusage">
																<children>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<properties valign="top"/>
																				<children>
																					<template subtype="attribute" match="service">
																						<children>
																							<content/>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<properties valign="top"/>
																				<children>
																					<template subtype="element" match="ub:rateschedule">
																						<children>
																							<content/>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<tgrid>
																						<properties align="right" border="0" width="100%"/>
																						<children>
																							<tgridbody-cols>
																								<children>
																									<tgridcol/>
																									<tgridcol/>
																									<tgridcol/>
																								</children>
																							</tgridbody-cols>
																							<tgridbody-rows>
																								<children>
																									<template subtype="element" match="ub:usage">
																										<children>
																											<tgridrow>
																												<children>
																													<tgridcell>
																														<children>
																															<template subtype="element" match="ub:description">
																																<children>
																																	<content/>
																																</children>
																																<variables/>
																															</template>
																														</children>
																													</tgridcell>
																													<tgridcell>
																														<properties align="right"/>
																														<children>
																															<template subtype="element" match="ub:quantity">
																																<children>
																																	<content/>
																																</children>
																																<variables/>
																															</template>
																														</children>
																													</tgridcell>
																													<tgridcell>
																														<properties align="left"/>
																														<children>
																															<template subtype="element" match="ub:quantity">
																																<children>
																																	<template subtype="attribute" match="units">
																																		<children>
																																			<content/>
																																		</children>
																																		<variables/>
																																	</template>
																																</children>
																																<variables/>
																															</template>
																														</children>
																													</tgridcell>
																												</children>
																											</tgridrow>
																										</children>
																										<variables/>
																									</template>
																								</children>
																							</tgridbody-rows>
																						</children>
																					</tgrid>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<properties align="right"/>
																				<children>
																					<template subtype="element" match="ub:total">
																						<children>
																							<content/>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																		</children>
																	</tgridrow>
																</children>
																<variables/>
															</template>
														</children>
														<variables/>
													</template>
												</children>
											</tgridbody-rows>
										</children>
									</tgrid>
									<newline/>
									<newline/>
									<newline/>
									<newline/>
									<newline/>
									<newline/>
									<newline/>
								</children>
							</paragraph>
							<newline/>
							<newline/>
							<condition>
								<children>
									<conditionbranch xpath="child::utilitybill/usagehistory/usage">
										<children>
											<paragraph>
												<children>
													<paragraph paragraphtag="h2">
														<children>
															<text fixtext="Usage History"/>
														</children>
													</paragraph>
													<tgrid>
														<properties align="left" border="0" width="100%"/>
														<children>
															<tgridbody-cols>
																<children>
																	<tgridcol>
																		<properties align="left"/>
																	</tgridcol>
																	<tgridcol>
																		<properties align="left"/>
																	</tgridcol>
																	<tgridcol/>
																	<tgridcol>
																		<properties align="left"/>
																	</tgridcol>
																</children>
															</tgridbody-cols>
															<tgridheader-rows>
																<children>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<children>
																					<paragraph paragraphtag="h3">
																						<children>
																							<text fixtext="Date"/>
																						</children>
																					</paragraph>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<paragraph paragraphtag="h3">
																						<children>
																							<text fixtext="Days"/>
																						</children>
																					</paragraph>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<tgrid>
																						<properties border="0" width="100%"/>
																						<children>
																							<tgridbody-cols>
																								<children>
																									<tgridcol>
																										<properties align="left"/>
																									</tgridcol>
																									<tgridcol>
																										<properties align="left"/>
																									</tgridcol>
																									<tgridcol>
																										<properties align="left"/>
																									</tgridcol>
																								</children>
																							</tgridbody-cols>
																							<tgridbody-rows>
																								<children>
																									<tgridrow>
																										<children>
																											<tgridcell>
																												<children>
																													<paragraph paragraphtag="h3">
																														<children>
																															<text fixtext="Identifier"/>
																														</children>
																													</paragraph>
																												</children>
																											</tgridcell>
																											<tgridcell>
																												<children>
																													<paragraph paragraphtag="h3">
																														<children>
																															<text fixtext="Amount"/>
																														</children>
																													</paragraph>
																												</children>
																											</tgridcell>
																											<tgridcell/>
																										</children>
																									</tgridrow>
																								</children>
																							</tgridbody-rows>
																						</children>
																					</tgrid>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<paragraph paragraphtag="h3">
																						<children>
																							<text fixtext="Total"/>
																						</children>
																					</paragraph>
																				</children>
																			</tgridcell>
																		</children>
																	</tgridrow>
																</children>
															</tgridheader-rows>
															<tgridbody-rows>
																<children>
																	<template subtype="element" match="ub:utilitybill">
																		<children>
																			<template subtype="element" match="ub:usagehistory">
																				<children>
																					<template subtype="element" match="ub:usage">
																						<children>
																							<tgridrow>
																								<children>
																									<tgridcell>
																										<children>
																											<template subtype="element" match="ub:date">
																												<children>
																													<content>
																														<format datatype="date"/>
																													</content>
																												</children>
																												<variables/>
																											</template>
																										</children>
																									</tgridcell>
																									<tgridcell>
																										<children>
																											<template subtype="element" match="ub:days">
																												<children>
																													<content>
																														<format datatype="integer"/>
																													</content>
																												</children>
																												<variables/>
																											</template>
																										</children>
																									</tgridcell>
																									<tgridcell>
																										<children>
																											<template subtype="element" match="ub:register">
																												<children>
																													<tgrid>
																														<properties border="0" width="100%"/>
																														<children>
																															<tgridbody-cols>
																																<children>
																																	<tgridcol>
																																		<properties align="left"/>
																																	</tgridcol>
																																	<tgridcol>
																																		<properties align="right"/>
																																	</tgridcol>
																																	<tgridcol>
																																		<properties align="left"/>
																																	</tgridcol>
																																</children>
																															</tgridbody-cols>
																															<tgridbody-rows>
																																<children>
																																	<tgridrow>
																																		<children>
																																			<tgridcell>
																																				<children>
																																					<template subtype="element" match="ub:identifier">
																																						<children>
																																							<content/>
																																						</children>
																																						<variables/>
																																					</template>
																																				</children>
																																			</tgridcell>
																																			<tgridcell>
																																				<children>
																																					<template subtype="element" match="ub:total">
																																						<children>
																																							<content/>
																																						</children>
																																						<variables/>
																																					</template>
																																				</children>
																																			</tgridcell>
																																			<tgridcell>
																																				<children>
																																					<template subtype="element" match="ub:total">
																																						<children>
																																							<template subtype="attribute" match="units">
																																								<children>
																																									<content/>
																																								</children>
																																								<variables/>
																																							</template>
																																						</children>
																																						<variables/>
																																					</template>
																																				</children>
																																			</tgridcell>
																																		</children>
																																	</tgridrow>
																																</children>
																															</tgridbody-rows>
																														</children>
																													</tgrid>
																												</children>
																												<variables/>
																											</template>
																										</children>
																									</tgridcell>
																									<tgridcell>
																										<children>
																											<template subtype="element" match="ub:total">
																												<children>
																													<content/>
																												</children>
																												<variables/>
																											</template>
																										</children>
																									</tgridcell>
																								</children>
																							</tgridrow>
																						</children>
																						<variables/>
																					</template>
																				</children>
																				<variables/>
																			</template>
																		</children>
																		<variables/>
																	</template>
																</children>
															</tgridbody-rows>
														</children>
													</tgrid>
													<newline/>
												</children>
											</paragraph>
										</children>
									</conditionbranch>
								</children>
							</condition>
							<newline/>
							<newline/>
							<newline/>
						</children>
						<variables/>
					</template>
				</children>
			</globaltemplate>
		</children>
	</mainparts>
	<globalparts/>
	<pagelayout>
		<properties paperheight="11.69in" paperwidth="8.27in"/>
	</pagelayout>
	<designfragments/>
</structure>
