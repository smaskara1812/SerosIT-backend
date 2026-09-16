Pls make a common function to send mail

And add the parameters  Debug_Email_Id, Mail_From_Address_Of_Logged_In_User at form level.


string strDebugModeYN = ConfigurationManager.ConnectionStrings["DebugModeYN"].ToString();
 

1) The local testing email has been sent to this ID
objSend_Mail._Debug_Email_Id = "savita.bodake@seros.co.in";

2) Use the logged-in user's email as the sender address. If its “Y”
objSend_Mail._Mail_From_Address_Of_Logged_In_User = "Y";

Select Mail_From_Address, Mail_User_Name ,Mail_User_Password From    dbo.Mst_Business_System where Business_System_id=6; 


 

 

if (_Mail_From_Address_Of_Logged_In_User == "Y")
{
	Select User_Email [Mail_From_Address], User_Login_Id [Mail_User_Name]  
	From dbo.Mst_User Where User_Id = 28065
}


 
  
Save User password @ login screen 








 
 
 
/*declare @strTo_Recipients  varchar(5000)
declare @strSystem_Owner_Email varchar(100) 
 
declare @strCc_Recipients varchar(5000)   
declare @strBcc_Recipients varchar(5000)   
declare @strMail_Subject varchar(5000)   
exec Prc_Email_Config @Alert_Id= 175 ,@strTo_Recipients=@strTo_Recipients out,
@strCc_Recipients = @strCc_Recipients out,@strBcc_Recipients=@strBcc_Recipients out,
@strMail_Subject = @strMail_Subject out

select @strTo_Recipients
select @strCc_Recipients
select @strBcc_Recipients
select @strMail_Subject
 */ 
ALTER PROCEDURE [dbo].[Prc_Email_Config]
@Alert_Id smallint,
@strSystem_Owner_Email varchar(100) = null,
@strTo_Recipients varchar(5000) out,
@strCc_Recipients varchar(5000) out,
@strBcc_Recipients varchar(5000) out,
@strMail_Subject varchar(1000) out,
@strAdditional_Alert char (1)= null out,
--@strAdditional_Alert_Freq tinyint=null out,
--@strAdditional_Alert_Mail_Dt datetime=null out,
@strAlert_Active char(1)=null out,
@strRead_Receipt_Recipient varchar(250)  =null  out
As

declare @Business_System_Id tinyint;
declare @Alert_Type char(1);
   Select 
		 @strTo_Recipients  = coalesce(@strTo_Recipients + Email_Addr , Email_Addr ) + ';'
   From dbo.Mail_Alert_To_User 
   Where Alert_Id = @Alert_Id 
        And Mail_Alert_To is Null
        And Addressee_Type = 'T'
        Order by IsNull(Mail_Alert_Order , 255 )
        
   Select  
		@strCc_Recipients  = coalesce(@strCc_Recipients + Email_Addr , Email_Addr ) + ';'
   From dbo.Mail_Alert_To_User 
   Where Alert_Id = @Alert_Id 
        And Mail_Alert_To is Null
        And Addressee_Type = 'C'
        Order by IsNull(Mail_Alert_Order , 255 )
        
   Select 
		 @strBcc_Recipients  = coalesce(@strBcc_Recipients + Email_Addr , Email_Addr ) + ';'
   From dbo.Mail_Alert_To_User 
   Where Alert_Id = @Alert_Id 
        And Mail_Alert_To is Null
        And Addressee_Type = 'B'
        Order by IsNull(Mail_Alert_Order , 255 )        
 
 Select  
		@strMail_Subject  = 
		Mail_Subject ,
		@strAdditional_Alert = 
		Additional_Alert,
		@strSystem_Owner_Email = 
		dbo.Fnc_Get_Col_Value('dbo.Mst_Employee', Owner_Emp_Id, 'EMAIL'),
		--@strAdditional_Alert_Freq=Alert_Freq,
		--@strAdditional_Alert_Mail_Dt=Next_Mail_Dt,
		@strAlert_Active=Alert_Active,
		@Business_System_Id = AD.Business_System_Id,
		@Alert_Type =  Alert_Type
   From dbo.Mail_Alert_Dtl AD, dbo.Mst_Business_System  BS
   Where Alert_Id = @Alert_Id
   and AD.Business_System_Id = BS.Business_System_id 
   
   /*   
   
    1) read receipt dont set for Addressee_Type='T' (To),(Done through FORM)
	2) READ RECIPET  allowed ofr only ONE USER So Set AS Y from the CC BCC to only one User

   */
	select
		@strRead_Receipt_Recipient = EMAIL_Addr 
	from dbo.Mail_Alert_To_User 
	where  Alert_Id = @Alert_Id and Read_Receipt='Y'  
 
		 IF ( @strTo_Recipients is null and @strCc_Recipients is null and @strBcc_Recipients is null)
		 BEGIN
				SET @strTo_Recipients = @strSystem_Owner_Email  + ';'

		 

				--changes on 22/07/2015
				IF(@Business_System_Id = 6)
				BEGIN 

					 SET @strTo_Recipients = 'Savita.Bodake@acerinox.co.in;'
					 IF(@Alert_Type = 'U')
					  BEGIN
			 				 set @strMail_Subject = @strMail_Subject	
					  end
					  ELSE
					  BEGIN
					   set @strMail_Subject = '0 user mapped in Mail_Alert_To_User -> '+@strMail_Subject
					  END
				END
		 
				ELSE
				BEGIN
					set @strMail_Subject = '0 user mapped in Mail_Alert_To_User -> '+@strMail_Subject
				END
		 end
	
	 
	
----------------------end 





/*
declare @strTo_Recipients1 VARCHAR(5000)     
declare @strCc_Recipients1 VARCHAR(5000)    
declare @strBcc_Recipients1 VARCHAR(5000)    

exec eos.Prc_Approval_Code
@Record_Status='Get_Email_Ids',
@Rig_Id=3,
@Dept_Id=119,
@MR_Hdr_Id=2703,
@Approval_Code='MR_ON',
@DB_USER_TYPE='CREATOR

@Event_Type='FINALIZE',
@Cur_Logged_In_User_Id=28069,--store mr10
@strTo_Recipients = @strTo_Recipients1 out,
@strCc_Recipients=@strCc_Recipients1 out,
@strBcc_Recipients=@strBcc_Recipients1 out
select @strTo_Recipients1,@strCc_Recipients1,@strBcc_Recipients1

declare @strTo_Recipients1 VARCHAR(5000)     
declare @strCc_Recipients1 VARCHAR(5000)    
declare @strBcc_Recipients1 VARCHAR(5000)    

exec eos.Prc_Approval_Code
@Record_Status='Get_Email_Ids',
@Rig_Id=3,
@Dept_Id=119,
@MR_Hdr_Id=2703,
@Approval_Code='MR_ON',
@DB_USER_TYPE='APPROVER_1', --='APPROVER_2'
@Event_Type='FINALIZE',
@Cur_Logged_In_User_Id=28232,
@strTo_Recipients = @strTo_Recipients1 out,
@strCc_Recipients=@strCc_Recipients1 out,
@strBcc_Recipients=@strBcc_Recipients1 out
select @strTo_Recipients1,@strCc_Recipients1,@strBcc_Recipients1

exec eos.Prc_Approval_Code
@Record_Status='Get_Email_Ids',
@Rig_Id=14,
@Dept_Id=6,
@MR_Hdr_Id=1671,
@Approval_Code='MR_ON',
@DB_USER_TYPE='APPROVER_1',
@Event_Type='FINALIZE',



@Cur_Logged_In_User_Id=28132
--USER_ID	USER_NAME 28065	Nidhin  Kakotil
exec eos.invoic
@Record_Status='Get_Email_Ids',
@Rig_Id=2,
@Dept_Id=6,
@SR_Hdr_Id=1,
@Approval_Code='SR_ON',
@DB_USER_TYPE='APPROVER_2',
@Event_Type='REVISE',--'FINALIZE',
@Cur_Logged_In_User_Id=418
---------------------
declare @strTo_Recipients1 VARCHAR(5000)     
declare @strCc_Recipients1 VARCHAR(5000)    
declare @strBcc_Recipients1 VARCHAR(5000)    

exec eos.Prc_Approval_Code
@Record_Status='Get_Email_Ids',
@Rig_Id=13,
@Dept_Id=119,
@MR_Hdr_Id=82,
@Approval_Code='MR_ON',
@DB_USER_TYPE='CREATOR',
@Event_Type='FINALIZE',
@Cur_Logged_In_User_Id=28079,
@strTo_Recipients = @strTo_Recipients1 out,
@strCc_Recipients=@strCc_Recipients1 out,
@strBcc_Recipients=@strBcc_Recipients1 out
select @strTo_Recipients1,@strCc_Recipients1,@strBcc_Recipients1


exec eos.Prc_Approval_Code
@Record_Status='Get_Email_Ids_Offer_Contract_Letters',
@Rig_Id=1,
@Fs_Contract_Hdr_Id=1111,
@Approval_Code='CONTRACT_LETTER',
@DB_USER_TYPE='CREATOR',
@Event_Type='FINALIZE',
@Cur_Logged_In_User_Id=470

*/
 
 
ALTER Procedure [eos].[Prc_Approval_Code]
(
		@Approval_Code_Id As  smallint=Null OutPut ,
		@Approval_Code As  varchar (25)=Null ,
		@Approval_Desc As  varchar (150)=Null ,
		@Cr_User_Id As  smallint=Null ,
		@Mod_User_Id As  smallint=Null ,
		@Approval_Active AS varchar(10)=null,
		@Record_Status Varchar(50),
		 
		@Rig_id As  smallint=Null ,
		@Dept_Id As  smallint=Null ,
		@DB_USER_TYPE VARCHAR(100)='',

		@DB_USER_TYPE_Approval_Status char(1)='',/*In INvoice_hdr depending upon A & R email list will be generated*/

		@Event_Type varchar(100)='',
		@Cur_Logged_In_User_Id INT =null,
		
		/*SR and MR*/
		@MR_Hdr_Id As  smallint=Null,
		@SR_Hdr_Id As  smallint=Null,

		/*Offer and Contract*/
		@Fs_New_Appl_Id as int=null,
        @Fs_Contract_Hdr_Id as int=null,		
		/*Rig Imprest revision*/
		@Rig_Imprest_Id smallint =null,

		/*OPC_Material_Cost*/
		@Material_Cost_Id	smallint =null,

		/*Inovice Hdr*/

		@Invoice_Hdr_Id 	smallint =null,
		@Grn_Hdr_Id  smallint=null,

		/*Overtime dtl*/
		@Overtime_Dtl_Id int=null,
		@strTo_Recipients VARCHAR(5000)= NULL  OUT ,
		@strCc_Recipients VARCHAR(5000) = NULL OUT,
		@strBcc_Recipients VARCHAR(5000) = NULL  OUT ,
		@Error_Message varchar(100) = NULL  OUT  ,
		@SubFilter_Hierarchy as varchar(100)='',
		@Opened_For_Revision_By	SMALLINT  = NULL,

		/*Drilling Dtl*/
		@Drilling_Dtl_Id	smallint  = NULL,
		@MU_Id smallint =null,

		@strOvertime_Dtl_Ids varchar(5000)=NULL
)

As
Begin 

If (@Record_Status ='Insert')
	Begin
		Set  @Approval_Code_Id= (Select IsNull(MAX(Approval_Code_Id),0)+1 From eos.Approval_Code)
		Insert Into eos.Approval_Code
			( Approval_Code_Id , Approval_Code , Approval_Desc , Cr_User_Id )
		Values
			( @Approval_Code_Id , @Approval_Code , @Approval_Desc , @Cr_User_Id )
	End

Else If (@Record_Status ='Select')
	Begin
		Select
			Approval_Code_Id ,Approval_Code ,Approval_Desc, Approval_Active
		From eos.Approval_Code
		Where Approval_Code_Id=@Approval_Code_Id
	END

ELSE IF (@Record_Status ='Update')
	BEGIN

		UPDATE eos.Approval_Code
		SET 
			Approval_Desc   = @Approval_Desc,
			Approval_Active = @Approval_Active,
			Mod_User_Id     = @Mod_User_Id,
			Mod_Dt			= getdate()		
		Where Approval_Code_Id = @Approval_Code_Id;	

	End


ELSE IF (@RECORD_STATUS ='DELETE')
	BEGIN
		DELETE FROM eos.Approval_Code WHERE Approval_Code_Id=@Approval_Code_Id;
	END

/*
Note : this mechanism is common for the offer letter ,  contact letter ,MR and SR ,Rig imprest

--------------------------------------------------------------------------------------------------
----------------Rig is used for Rig imprest only in other case its not required-------------------
--------------------------------------------------------------------------------------------------
As little change in Rig Imprest that when user login details are get..
same time check that if the user is approver 1 then check that 
user have Approver rights for that Rig
--------------------------------------------------------------------------------------------------
*/
ELSE IF (@Record_Status ='Get_Login_User_Details' or @Record_Status ='Get_Login_User_Details_Multiple_Roles')
BEGIN 		 
 

				DECLARE @CNT INT =0;
				DECLARE @Emp_id INT =0;
				DECLARE @NONEMP_ID INT =0;
 	                declare @Create_Yn char(1)='N';

				DECLARE @EmpType varchar(100)='NON_EMP';
				--////////////////////////////////
				SELECT  @Emp_id = EMP_ID  FROM dbo.Mst_User WHERE  USER_ID  = @Cur_Logged_In_User_Id;
				SELECT  @NONEMP_ID = NONEMP_ID  FROM dbo.Mst_User WHERE  USER_ID  = @Cur_Logged_In_User_Id;

				IF( @Emp_id IS NOT NULL)----Employee
				BEGIN

					DECLARE @Working_Designation_Id int = 0;
					SELECT @Working_Designation_Id =  Working_Designation_Id from dbo.Mst_Employee 
					WHERE   EMP_ID =  @Emp_id  ; 
					set @EmpType = 'EMP'
				END 

				 
				--////////////////////////////////
				DECLARE @Login_User_Type VARCHAR(50)=''
				IF EXISTS(SELECT 1 FROM  eos.Approver_Mapping map inner join eos.Approval_Code cod on  map.Approval_Code_Id=  cod.Approval_Code_Id				
				where  Approver_User_Id = @Cur_Logged_In_User_Id  and Approver_Level = 1 
				and Approver_Active= 'Y' and Approval_Active ='Y' and Approval_Code = @Approval_Code) 
				BEGIN
						 SET @Login_User_Type ='APPROVER_1';
						 
						 --This is hardcoded as in OFFER_LETTER  / CONTRACT_LETTER Approver can be creator...

						IF(@Approval_Code ='OFFER_LETTER' OR @Approval_Code ='CONTRACT_LETTER' OR @Approval_Code ='DRILLING_DTL'  OR @Approval_Code ='MUTUAL_UNDERSTAND')
						BEGIN
				              SET @Login_User_Type = 'CREATOR'+','+@Login_User_Type 
						END
						 
						--this is added NEW case
						--it will call only in case of inVOICE hdr for now.

						if (@Rig_Id IS NOT NULL)
						BEGIN
							  IF EXISTS
							    (   SELECT 1 FROM   
									eos.Approver_Mapping map 
									INNER JOIN eos.Approval_Code cod on  map.Approval_Code_Id=  cod.Approval_Code_Id				
									INNER JOIN eos.Approver_Mapping_Dtl  appv_user on appv_user.Approver_Mapping_Id  = map.Approver_Mapping_Id
									where  Approver_User_Id = @Cur_Logged_In_User_Id  and Approver_Level = 1 
									AND Approver_Active= 'Y' and Approval_Active ='Y' and Approval_Code = @Approval_Code
									AND Rig_Id =  @Rig_Id  
								 )
							
								SELECT 
								   @Create_Yn = Create_Yn
								FROM   
								eos.Approver_Mapping map 
								INNER JOIN eos.Approval_Code cod on  map.Approval_Code_Id=  cod.Approval_Code_Id				
								INNER JOIN eos.Approver_Mapping_Dtl  appv_user on appv_user.Approver_Mapping_Id  = map.Approver_Mapping_Id
								where  Approver_User_Id = @Cur_Logged_In_User_Id  and Approver_Level = 1 
								AND Approver_Active= 'Y' and Approval_Active ='Y' and Approval_Code = @Approval_Code
								AND Rig_Id =  @Rig_Id;  
								 
						END
						 
						
				END 
				ELSE IF EXISTS(SELECT 1 FROM eos.Approver_Mapping map INNER JOIN eos.Approval_Code cod on  map.Approval_Code_Id=  cod.Approval_Code_Id
				WHERE  Approver_User_Id = @Cur_Logged_In_User_Id  and Approver_Level=2
				AND Approver_Active= 'Y' and Approval_Active ='Y' and Approval_Code = @Approval_Code) 
				BEGIN

			----	select 'sVITA:',CAST (@Cur_Logged_In_User_Id AS VARCHaR(100)), @Approval_Code
						SET @Login_User_Type ='APPROVER_2';

							--this is added NEW case
						--it will call only in case of inVOICE hdr for now
						if (@Rig_Id is NOT NULL)
						BEGIN
							IF EXISTS(SELECT 1 FROM   
									eos.Approver_Mapping map 
									INNER JOIN eos.Approval_Code cod on  map.Approval_Code_Id=  cod.Approval_Code_Id				
									INNER JOIN eos.Approver_Mapping_Dtl  appv_user on appv_user.Approver_Mapping_Id  = map.Approver_Mapping_Id
									where  Approver_User_Id = @Cur_Logged_In_User_Id  AND Approver_Level = 2 
									AND Approver_Active= 'Y' and Approval_Active ='Y' AND Approval_Code = @Approval_Code
									AND Rig_Id =  @Rig_Id 
 
								)
							
								SELECT 
								   @Create_Yn = Create_Yn
								FROM   
								eos.Approver_Mapping map 
								INNER JOIN eos.Approval_Code cod on  map.Approval_Code_Id=  cod.Approval_Code_Id				
								INNER JOIN eos.Approver_Mapping_Dtl  appv_user on appv_user.Approver_Mapping_Id  = map.Approver_Mapping_Id
								where  Approver_User_Id = @Cur_Logged_In_User_Id  and Approver_Level = 2 
								AND Approver_Active= 'Y' and Approval_Active ='Y' and Approval_Code = @Approval_Code
								AND Rig_Id =  @Rig_Id 

								 
						END
				END  
				ELSE IF EXISTS(SELECT 1 FROM   eos.Approver_Mapping map inner join eos.Approval_Code cod on  map.Approval_Code_Id=  cod.Approval_Code_Id
				WHERE  Approver_User_Id = @Cur_Logged_In_User_Id  and Approver_Level=3
				AND Approver_Active= 'Y' and Approval_Active ='Y' and Approval_Code = @Approval_Code) 
				BEGIN
						SET @Login_User_Type ='APPROVER_3';

							--this is added NEW case
						--it will call only in case of inVOICE hdr for now
						if (@Rig_Id is NOT NULL)
						BEGIN
							IF EXISTS(SELECT 1 FROM   
									eos.Approver_Mapping map 
									inner join eos.Approval_Code cod on  map.Approval_Code_Id=  cod.Approval_Code_Id				
									inner join eos.Approver_Mapping_Dtl  appv_user on appv_user.Approver_Mapping_Id  = map.Approver_Mapping_Id
									where  Approver_User_Id = @Cur_Logged_In_User_Id  and Approver_Level = 3 
									and Approver_Active= 'Y' and Approval_Active ='Y' and Approval_Code = @Approval_Code
									AND Rig_Id =  @Rig_Id  
								)
							
								SELECT 
								   @Create_Yn = Create_Yn
								FROM   
								eos.Approver_Mapping map 
								INNER JOIN eos.Approval_Code cod on  map.Approval_Code_Id=  cod.Approval_Code_Id				
								INNER JOIN eos.Approver_Mapping_Dtl  appv_user on appv_user.Approver_Mapping_Id  = map.Approver_Mapping_Id
								where  Approver_User_Id = @Cur_Logged_In_User_Id  and Approver_Level = 3 
								AND Approver_Active= 'Y' and Approval_Active ='Y' and Approval_Code = @Approval_Code
								AND Rig_Id =  @Rig_Id 

								 
						END
				END  
				ELSE 
				BEGIN
						SET @Login_User_Type ='CREATOR';
						set @Create_Yn ='Y';
				end 
			
				DECLARE @Logged_In_User_Email_Id  Varchar(200); 
				SELECT @Logged_In_User_Email_Id  = User_Email from dbo.Mst_User where USER_ID = @Cur_Logged_In_User_Id					

				 
  
				--------------------------------------------------------------------------------
 				SELECT 

				@Login_User_Type[Logged_In_User_Type],@Create_Yn  Create_Yn,

				case when @EmpType='EMP'then
				dbo.Fnc_Get_Col_Value('dbo.Mst_Employee',@Emp_id,'NAME')
				
				else
				hr.Fnc_Get_Col_Value('hr.Mst_NonEmployee',@NONEMP_ID,'NAME')
				end as 			[Logged_In_User_Name],
				dbo.Fnc_Get_Col_Value('dbo.Mst_Working_Designation',@Working_Designation_Id,'NAME')
				[Logged_In_User_Name_Designation],
				@Working_Designation_Id [Logged_In_Working_Designation_Id],
				@EmpType [Emp_Or_Non_Emp],@Cur_Logged_In_User_Id [Logged_In_User_Id]--
					
	  END 
ELSE IF (@Record_Status ='Get_Email_Ids')
BEGIN
	 
		CREATE TABLE #All_Data ([Ord] int,Email_Addr varchar(300),Types  varchar(300),Addressee_Type varchar(300))
		/*--------------------------------------------------------------------------------------------------------------------*/
		/*For level 1 : only the RIG is considered*/
		SELECT  
			1 [Ord],	dbo.Fnc_Get_Col_Value('dbo.Mst_User',Approver_User_Id,'EMAIl')Email_Addr,
			'APPROVER_1'[Type] ,'C' [Addressee_Type] 
			into #Temp_Approver_1 from  eos.Approver_Mapping map 
			INNER JOIN eos.Approval_Code cod on  map.Approval_Code_Id=cod.Approval_Code_Id
			INNER JOIN  eos.Approver_Mapping_Dtl mapApprover  on mapApprover.Approver_Mapping_Id = map.Approver_Mapping_Id
		WHERE Approver_Level= 1 
		and Approver_Active= 'Y' and Approval_Active ='Y' and Approval_Code = @Approval_Code and 
		((@DB_USER_TYPE  ='CREATOR' AND Receive_Mail = 'Y') OR  (@DB_USER_TYPE <> 'CREATOR' AND Receive_Mail = 'Y'))/*this can be MR_ON or SR_ON*/
		and Dept_Id is null 
		and Rig_Id = @Rig_Id 
		
		/*For level 2 : RIG and DEPARTMENT is considered*/
		SELECT  
			1 [Ord],	dbo.Fnc_Get_Col_Value('dbo.Mst_User',Approver_User_Id,'EMAIl')Email_Addr,
			'APPROVER_2'[Type] ,'C' [Addressee_Type] 
			into #Temp_Approver_2 from  eos.Approver_Mapping map 
			INNER JOIN eos.Approval_Code cod on  map.Approval_Code_Id=cod.Approval_Code_Id
			INNER JOIN  eos.Approver_Mapping_Dtl mapApprover  on mapApprover.Approver_Mapping_Id = map.Approver_Mapping_Id
		WHERE Approver_Level= 2 
		AND Approver_Active= 'Y' AND Approval_Active ='Y' AND Approval_Code = @Approval_Code   and 
		
		((@DB_USER_TYPE  ='CREATOR' AND Receive_Mail = 'Y') OR ( @DB_USER_TYPE <> 'CREATOR' AND Receive_Mail = 'Y'))/*this can be MR_ON or SR_ON*/
		AND Dept_Id = @Dept_Id  AND Rig_Id = @Rig_Id

		select * from  #Temp_Approver_1
		select *from #Temp_Approver_2
 		/*--------------------------------------------------------------------------------------------------------------------*/
			
		if(@Event_Type ='FINALIZE')
		BEGIN
					IF(@DB_USER_TYPE  ='CREATOR')
					BEGIN
						/*
						Alert_Ids
						-------------------------------------------------------    ---------------------------------------------------------
						|						MATERIAL					  |	   |		             SERVICE						   |
						-------------------------------------------------------    ---------------------------------------------------------

						| 209	Material Requisition : Creation Mail				213   Service Requisition : Creation Mail
						| 210	Material Requisition : Level 1 approver Mail		214   Service Requisition : Level 1 approver Mail
						| 208	Material Requisition : Level 2 approver Mail		215   Service Requisition : Level 2 approver Mail							
						| 211 Material Requisition : Revise by Level 1 approver		216   Service Requisition : Revise by Level 1 approver
						| 212 Material Requisition : Revise by Level 2 approver		217   Service Requisition : Revise by Level 2 approver
						-------------------------------------------------------    ---------------------------------------------------------
						*/ 
						
						INSERT INTO #All_Data 

						SELECT * FROM 
						(       /*Approver level 1*/
				 
								SELECT [Ord]  ,Email_Addr ,TYPE,'T' Addressee_Type FROM #Temp_Approver_1
						UNION 
							   /*Logged in User*/
								SELECT  2 [Ord] ,
								dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIl'),'Cur_Logged_In_User','C' [Addressee_Type]

						/*----------------------------------------------MR and SR both----------------------------------------------------*/		
						UNION
							  /*Employees added in alert table  MATERIAL*/
								SELECT  3 [Ord],
								 RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type  FROM dbo.Mail_Alert_To_User 
								WHERE Alert_Id = 209  AND Mail_Alert_To IS NULL AND @Approval_Code = 'MR_ON'

						UNION
							  /*Employees added in alert table  SERVICE*/
								SELECT  3 [Ord],
								 RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type  FROM dbo.Mail_Alert_To_User 
								WHERE Alert_Id = 213  AND Mail_Alert_To IS NULL AND @Approval_Code = 'SR_ON'
						/*-----------------------------------------------------------------------------------------------------------------*/		
						)tb
						ORDER BY [Ord]
		 
					END

					IF(@DB_USER_TYPE  ='APPROVER_1')
					BEGIN
					/*
					Alert_Ids
					208	Material Requisition : Level 2 approver Mail
					209	Material Requisition : Creation Mail
					210	Material Requisition : Level 1 approver Mail*/ 
						insert into #All_Data 

						SELECT * FROM   
						(       /*Approver level 1*/
							 SELECT [Ord]  ,Email_Addr ,Type,'T' Addressee_Type From #Temp_Approver_2

							 union

							  SELECT [Ord]  ,Email_Addr ,Type,'C' Addressee_Type From #Temp_Approver_1
								

								
							 /*----------------------------------------------MR and SR both----------------------------------------------------*/		
							 UNION
		
							 SELECT  2 [Ord] ,
								dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIL'),'MR_Created_By','C' [Addressee_Type]
								from eos.Material_Requisition_Hdr WHERE  MR_Hdr_Id = @MR_Hdr_Id

							 UNION
							 SELECT  2 [Ord] ,
								dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIL'),'SR_Created_By','C' [Addressee_Type]
								from eos.Service_Requisition_Hdr WHERE  SR_Hdr_Id = @SR_Hdr_Id
							/*-----------------------------------------------------------------------------------------------------------------*/		
							 UNION 
							    /*Logged in User*/
								SELECT  3 [Ord] ,
								dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIL'),'Cur_Logged_In_User','C' [Addressee_Type]

							 /*----------------------------------------------MR and SR both----------------------------------------------------*/	
							 UNION
							    /*Employees added in alert table MATERIAL*/
								SELECT  4 [Ord],
								RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type  FROM dbo.Mail_Alert_To_User 
								Where Alert_Id = 210  AND Mail_Alert_To IS NULL and @Approval_Code = 'MR_ON'

							 UNION
							    /*Employees added in alert table SERVICE*/
								SELECT  4 [Ord],
								RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type  FROM dbo.Mail_Alert_To_User 
								Where Alert_Id = 214  AND Mail_Alert_To IS NULL and @Approval_Code = 'SR_ON'
							/*-----------------------------------------------------------------------------------------------------------------*/		
						)tb
						order by [Ord]
		 
					END
 
					IF(@DB_USER_TYPE  ='APPROVER_2')
					BEGIN
					/*
					Alert_Ids
					208	Material Requisition : Level 2 approver Mail
					209	Material Requisition : Creation Mail
					210	Material Requisition : Level 1 approver Mail*/ 
						INSERT INTO #All_Data 

						SELECT * FROM   
						(       /*Approver level 1*/
							SELECT [Ord]  ,Email_Addr ,Type,'C' Addressee_Type From #Temp_Approver_1
							
							union
							SELECT [Ord]  ,Email_Addr ,Type,'C' Addressee_Type From #Temp_Approver_2
							
							/*----------------------------------------------MR and SR both----------------------------------------------------*/
							UNION		
								SELECT  2 [Ord] ,dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIL'),'MR_Created_By','C' [Addressee_Type]
								from eos.Material_Requisition_Hdr where  MR_Hdr_Id = @MR_Hdr_Id
							UNION		
								SELECT  2 [Ord] ,dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIL'),'SR_Created_By','C' [Addressee_Type]
								from eos.Service_Requisition_Hdr where  SR_Hdr_Id = @SR_Hdr_Id
							/*-----------------------------------------------------------------------------------------------------------------*/	
							UNION 
							   /*Logged in User*/
								SELECT  3 [Ord] ,dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIl'),'Cur_Logged_In_User','C' [Addressee_Type]

							/*----------------------------------------------MR and SR both----------------------------------------------------*/							
							UNION
							  /*Employees added in alert table MATERIAL*/
								SELECT  4 [Ord],RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type From dbo.Mail_Alert_To_User 
								Where Alert_Id = 208  AND Mail_Alert_To IS NULL and @Approval_Code = 'MR_ON'

							UNION
							  /*Employees added in alert table SERVICE*/
								SELECT  4 [Ord],RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type From dbo.Mail_Alert_To_User 
								Where Alert_Id = 215  AND Mail_Alert_To IS NULL and @Approval_Code = 'SR_ON'
							/*-----------------------------------------------------------------------------------------------------------------*/

							UNION 
   						    ----------------this changes are regarding to the email send to particular Email id---------------------------------

						   SELECT  5 [Ord],RTRIM(LTRIM(dbo.Fnc_Get_Col_Value('dbo.Mst_User' ,user_id,'EMAIL') )),'Rig_To_Email_Mapping',Addressee_Type
						    FROM eos.Rig_To_Email_Mapping 
							Where Alert_Id = 208  AND To_Dt IS NULL and Rig_Id =@Rig_Id  and @Approval_Code = 'MR_ON'

							UNION

					        SELECT  6 [Ord],RTRIM(LTRIM(dbo.Fnc_Get_Col_Value('dbo.Mst_User' ,user_id,'EMAIL') )),'Rig_To_Email_Mapping',Addressee_Type
						    From eos.Rig_To_Email_Mapping 
							Where Alert_Id = 215  AND To_Dt IS NULL  and Rig_Id =@Rig_Id and @Approval_Code = 'SR_ON'
						

						)tb
						order by [Ord]
		 
					END   
	
		END	

			
		IF(@Event_Type ='REVISE')
		BEGIN
							IF(@DB_USER_TYPE  ='APPROVER_1')
								BEGIN
								/*
									Alert_Ids:
									208	Material Requisition : Level 2 approver Mail
									209	Material Requisition : Creation Mail
									210	Material Requisition : Level 1 approver Mail
								*/ 
								INSERT INTO #All_Data 
								SELECT * FROM   
								(       
										 /*Approver level 1*/
										 SELECT [Ord], Email_Addr ,Type,'C' Addressee_Type FROM #Temp_Approver_2
										
										 /*----------------------------------------------MR and SR both--------------------------------------------------------------*/	
										 UNION												 
										 SELECT 2 [Ord], dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIl'),'MR_Created_By','T' [Addressee_Type]
										 FROM eos.Material_Requisition_Hdr WHERE  MR_Hdr_Id = @MR_Hdr_Id 										 
										 UNION		
		  								 SELECT 2 [Ord], dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIl'),'SR_Created_By','T' [Addressee_Type]
										 FROM eos.Service_Requisition_Hdr WHERE  SR_Hdr_Id = @SR_Hdr_Id 
										 /*--------------------------------------------------------------------------------------------------------------------------*/	

										 UNION 
										 /*Logged in User*/
										 SELECT 3 [Ord], dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIl'),'Cur_Logged_In_User','C' [Addressee_Type]

										 /*----------------------------------------------MR and SR both--------------------------------------------------------------*/	
										 UNION
										 /*Employees added in alert table MATERIAL*/
										 SELECT 4 [Ord], RTRIM(LTRIM(Email_Addr)),'DataBase', Addressee_Type  FROM dbo.Mail_Alert_To_User 
										 WHERE Alert_Id = 211  AND Mail_Alert_To IS NULL AND @Approval_Code = 'MR_ON'

										 UNION
										 /*Employees added in alert table SERVICE*/
										 SELECT 4 [Ord], RTRIM(LTRIM(Email_Addr)),'DataBase', Addressee_Type  From dbo.Mail_Alert_To_User 
										 WHERE Alert_Id = 216  AND Mail_Alert_To IS NULL AND @Approval_Code = 'SR_ON'
										/*----------------------------------------------------------------------------------------------------------------------------*/	
									)tb
									ORDER BY [Ord];		 
								END
 
								IF(@DB_USER_TYPE  ='APPROVER_2')
								BEGIN
								/*
								Alert_Ids
								208	Material Requisition : Level 2 approver Mail
								209	Material Requisition : Creation Mail
								210	Material Requisition : Level 1 approver Mail*/ 
									INSERT INTO #All_Data 
									SELECT * FROM   
									(       /*Approver level 1*/
											/*--------------------------------------------------------------------------------------------------------------------------*/
											SELECT [Ord]  ,Email_Addr ,Type,'C' Addressee_Type From #Temp_Approver_1
												
											/*----------------------------------------------MR and SR both--------------------------------------------------------------*/										
											UNION		 
											SELECT  2 [Ord] ,
											dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIl'),'MR_Created_By','T' [Addressee_Type]
											from eos.Material_Requisition_Hdr WHERE  MR_Hdr_Id = @MR_Hdr_Id

											
											UNION		 
											SELECT  2 [Ord] ,
											dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIl'),'SR_Created_By','T' [Addressee_Type]
											from eos.Service_Requisition_Hdr WHERE SR_Hdr_Id = @SR_Hdr_Id
											/*--------------------------------------------------------------------------------------------------------------------------*/
											UNION 
											/*Logged in User*/
											SELECT  3 [Ord] ,
											dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIl'),'Cur_Logged_In_User','C' [Addressee_Type]
												
												
											UNION
											/*Employees added in alert table MATERIAL*/
											SELECT  4 [Ord],
											RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type  FROM dbo.Mail_Alert_To_User 
											Where Alert_Id = 212  AND Mail_Alert_To IS NULL AND @Approval_Code = 'MR_ON'
											
											UNION
										    /*Employees added in alert table SERVICE*/
											SELECT  4 [Ord],
											RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type  FROM dbo.Mail_Alert_To_User 
											WHERE Alert_Id = 217  AND Mail_Alert_To IS NULL AND @Approval_Code = 'SR_ON'

											 UNION 
   											----------------this changes are regarding to the email send to particular Email id---------------------------------

										   SELECT  5 [Ord],RTRIM(LTRIM(dbo.Fnc_Get_Col_Value('dbo.Mst_User' ,user_id,'EMAIL') )),
										   'Rig_To_Email_Mapping',Addressee_Type
											FROM eos.Rig_To_Email_Mapping 
											Where Alert_Id = 212  AND To_Dt IS NULL  and Rig_Id =@Rig_Id  and @Approval_Code = 'MR_ON'

											UNION

											SELECT  6 [Ord],RTRIM(LTRIM(dbo.Fnc_Get_Col_Value('dbo.Mst_User' ,user_id,'EMAIL') )),
											'Rig_To_Email_Mapping',Addressee_Type
											From eos.Rig_To_Email_Mapping 
											Where Alert_Id = 217  AND To_Dt IS NULL and Rig_Id =@Rig_Id  and @Approval_Code = 'SR_ON'
						
											
									)tb
									ORDER BY [Ord]
		 
								END   
	
			 END;


			 
				select *,ROW_NUMBER() OVER(ORDER BY Email_Addr)[Orders],''[Addressee_Type] into #Distinct_Email_Addr_Temp
				from 
				(
						SELECT DISTINCT Email_Addr  FROM #All_Data 
				)tb  
				---------------

				----------------------------------------- select *  	FROM #All_Data 
					--DECLARE @Cnt int =1;
					SET  @Cnt =1;
					DECLARE @CntMAX int = 0;
					SELECT @CntMAX = COUNT(0) FROM #Distinct_Email_Addr_Temp;
					WHILE (@Cnt<=@CntMAX)
					BEGIN
					DECLARE @TmpEmail_Addr varchar(100)='';

						SELECT  @TmpEmail_Addr = Email_Addr
						FROM  #Distinct_Email_Addr_Temp where Orders=@Cnt;		 		  
						DECLARE @Send_Multi_Types  Varchar(7000)='';     									 


						SELECT
						
						      @Send_Multi_Types = COALESCE( @Send_Multi_Types +  CAST(Addressee_Type AS VARCHAR(100)),
						      CAST(Addressee_Type AS VARCHAR(100)) ) + ','  					
			 			
						FROM 
						(	 
							SELECT  Addressee_Type
							FROM  #All_Data  WHERE Email_Addr = @TmpEmail_Addr
						)tb
			
						SET @Send_Multi_Types = SUBSTRING(@Send_Multi_Types,0,LEN(@Send_Multi_Types)-0)		
						--Select @Send_Multi_Types,@TmpEmail_Addr;

						IF(LEN(@Send_Multi_Types)>1)
						BEGIN 

							 IF ( CHARINDEX('T',@Send_Multi_Types) > 0 )			    
							 BEGIN
									UPDATE #Distinct_Email_Addr_Temp set [Addressee_Type]='T' 
									WHERE  Orders=@Cnt;	
							 END
							 ELSE IF (CHARINDEX('C',@Send_Multi_Types) > 0 )
							 BEGIN
									UPDATE #Distinct_Email_Addr_Temp set [Addressee_Type]='C' 
									WHERE  Orders=@Cnt;	
							 END	
							 ELSE IF (CHARINDEX('B',@Send_Multi_Types) > 0 )
							 BEGIN
									UPDATE #Distinct_Email_Addr_Temp set [Addressee_Type]='B' 
									WHERE  Orders=@Cnt;	
							 END			 
						END
						ELSE
						BEGIN
							UPDATE #Distinct_Email_Addr_Temp set [Addressee_Type]=@Send_Multi_Types 
							WHERE  Orders=@Cnt;	
						END
						SET @Cnt= @Cnt+1; 
						SET @Send_Multi_Types = '';
						SET @TmpEmail_Addr =''
					END; 


			   SELECT 
					 @strTo_Recipients  = COALESCE(@strTo_Recipients + Email_Addr , Email_Addr ) + ';'
			   FROM #Distinct_Email_Addr_Temp   WHERE  Addressee_Type = 'T'; 

			   SELECT  
					@strCc_Recipients  =  coalesce(@strCc_Recipients + Email_Addr , Email_Addr ) + ';'
			   FROM #Distinct_Email_Addr_Temp   WHERE  Addressee_Type = 'C';

			   SELECT 
					 @strBcc_Recipients  = coalesce(@strBcc_Recipients + Email_Addr , Email_Addr ) + ';'
			   FROM #Distinct_Email_Addr_Temp   WHERE  Addressee_Type = 'B';


			   SELECT @strTo_Recipients,@strCc_Recipients,@strBcc_Recipients
			     
				IF ( @strTo_Recipients IS NULL )
				BEGIN
					SET @Error_Message ='E-Mail To address in not defined..'
				END

			----------------------- SELECT *FROM  #Distinct_Email_Addr_Temp	
			DROP TABLE #Distinct_Email_Addr_Temp;
			DROP TABLE #All_Data ;
			DROP TABLE #Temp_Approver_1;
			DROP TABLE #Temp_Approver_2;			
END
 --/////////////////////////////////////
ELSE IF (@Record_Status ='Get_Email_Ids_Offer_Contract_Letters')
BEGIN
	 
		CREATE TABLE #All_Data_Offer_Contract ([Ord] int,Email_Addr varchar(300),Types  varchar(300),Addressee_Type varchar(300))
		/*--------------------------------------------------------------------------------------------------------------------*/
		/*For level 1 : only the RIG is considered*/
		SELECT  
			1 [Ord],	dbo.Fnc_Get_Col_Value('dbo.Mst_User',Approver_User_Id,'EMAIl')Email_Addr,
			'APPROVER_1'[Type] ,'C' [Addressee_Type] 
			INTO #Temp_Approver_1_Offer_Contract from  eos.Approver_Mapping map 
			INNER JOIN eos.Approval_Code cod on  map.Approval_Code_Id=cod.Approval_Code_Id
			INNER JOIN  eos.Approver_Mapping_Dtl mapApprover  on mapApprover.Approver_Mapping_Id = map.Approver_Mapping_Id
		WHERE Approver_Level= 1 
		AND Approver_Active= 'Y' and Approval_Active ='Y' and Approval_Code = @Approval_Code and 
		((@DB_USER_TYPE  ='CREATOR' AND Receive_Mail = 'Y')  OR  (@DB_USER_TYPE <> 'CREATOR' AND Receive_Mail = 'Y'))/*this can be MR_ON or SR_ON*/
		AND Dept_Id IS NULL  AND Rig_Id = @Rig_Id 
		 
			
		if(@Event_Type ='FINALIZE')
		BEGIN
					IF(@DB_USER_TYPE  ='CREATOR' or  @DB_USER_TYPE  ='CREATOR,APPROVER_1') 
					BEGIN
						/*
						Alert_Ids
						-------------------------------------------------------    ---------------------------------------------------------
						|						Offer					  |	   |		             Contract						   |
						-------------------------------------------------------    ---------------------------------------------------------


						218		Offer Letter : Creation Mail					220	Contract Letter : Creation Mail
						219		Offer Letter : Level 1 approver Mail            221	Contract Letter : Level 1 approver Mail
					 
						-------------------------------------------------------    ---------------------------------------------------------
						*/ 
						
						INSERT INTO #All_Data_Offer_Contract 

						SELECT * FROM 
						(       /*Approver level 1*/
				 
								SELECT [Ord]  ,Email_Addr ,TYPE,'T' Addressee_Type FROM #Temp_Approver_1_Offer_Contract
						UNION 
							   /*Logged in User*/
								SELECT  2 [Ord] ,
								dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIl'),'Cur_Logged_In_User','C' [Addressee_Type]

						/*----------------------------------------------MR and SR both----------------------------------------------------*/		
						UNION
							  /*Employees added in alert table  MATERIAL*/
								SELECT  3 [Ord],
								 RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type  FROM dbo.Mail_Alert_To_User 
								WHERE Alert_Id = 218  AND Mail_Alert_To IS NULL AND @Approval_Code = 'OFFER_LETTER'

						UNION
							  /*Employees added in alert table  SERVICE*/
								SELECT  3 [Ord],
								 RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type  FROM dbo.Mail_Alert_To_User 
								WHERE Alert_Id = 220  AND Mail_Alert_To IS NULL AND @Approval_Code = 'CONTRACT_LETTER'
						/*-----------------------------------------------------------------------------------------------------------------*/		
						)tb
						ORDER BY [Ord]
		 
					END

					IF(@DB_USER_TYPE  ='APPROVER_1' or  @DB_USER_TYPE  ='CREATOR,APPROVER_1') 
					BEGIN
					/*
					Alert_Ids
					208	Material Requisition : Level 2 approver Mail
					209	Material Requisition : Creation Mail
					210	Material Requisition : Level 1 approver Mail*/ 
						INSERT INTO #All_Data_Offer_Contract 

						SELECT * FROM   
						(       /*Approver level 1*/
							 SELECT [Ord]  ,Email_Addr ,Type,'T' Addressee_Type From #Temp_Approver_1_Offer_Contract 	
							 /*----------------------------------------------MR and SR both----------------------------------------------------*/		
							 UNION
		
							 SELECT  2 [Ord] ,
								dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIL'),'Offer_Created_By','T' [Addressee_Type]
								from eos.Fs_Offer_Letter WHERE  Fs_New_Appl_Id = @Fs_New_Appl_Id

							 UNION
							 SELECT  2 [Ord] ,
								dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIL'),'Contract_Created_By','T' [Addressee_Type]
								from eos.Fs_Contract_Hdr WHERE  Fs_Contract_Hdr_Id = @Fs_Contract_Hdr_Id 
							/*-----------------------------------------------------------------------------------------------------------------*/		
							 UNION 
							    /*Logged in User*/
								SELECT  3 [Ord] ,
								dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIL'),'Cur_Logged_In_User','C' [Addressee_Type]

							 /*----------------------------------------------Mail_Alert_To_User----------------------------------------------------*/	
							 UNION
							    /*Employees added in alert table MATERIAL*/
								SELECT  4 [Ord],
								RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type  FROM dbo.Mail_Alert_To_User 
								Where Alert_Id = 219  AND Mail_Alert_To IS NULL and @Approval_Code = 'OFFER_LETTER'

							 UNION
							    /*Employees added in alert table SERVICE*/
								SELECT  4 [Ord],
								RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type  FROM dbo.Mail_Alert_To_User 
								Where Alert_Id = 221  AND Mail_Alert_To IS NULL and @Approval_Code = 'CONTRACT_LETTER'
							/*-----------------------------------------------------------------------------------------------------------------*/		
						)tb
						order by [Ord]
		 
					END
  
	
		END	  


		if(@Event_Type ='REVISE')
		BEGIN
					 
					IF(@DB_USER_TYPE  ='APPROVER_1' or  @DB_USER_TYPE  ='CREATOR,APPROVER_1') 
					BEGIN
					/*
					 */ 
						INSERT INTO #All_Data_Offer_Contract 

						SELECT * FROM   
						(       /*Approver level 1*/
							 SELECT [Ord]  ,Email_Addr ,Type,'T' Addressee_Type From #Temp_Approver_1_Offer_Contract 	
							 /*----------------------------------------------MR and SR both----------------------------------------------------*/		
							 UNION
		
							 SELECT  2 [Ord] ,
								dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIL'),'Offer_Created_By','T' [Addressee_Type]
								from eos.Fs_Offer_Letter WHERE  Fs_New_Appl_Id = @Fs_New_Appl_Id

							/*-----------------------------------------------------------------------------------------------------------------*/		
							 UNION 
							    /*Logged in User*/
								SELECT  3 [Ord] ,
								dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIL'),'Cur_Logged_In_User','C' [Addressee_Type]

							 /*----------------------------------------------Mail_Alert_To_User----------------------------------------------------*/	
							 --UNION
							 --   /*NO need to add this for now 01/08/2020*/
								--SELECT  4 [Ord],
								--RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type  FROM dbo.Mail_Alert_To_User 
								--Where Alert_Id = 219  AND Mail_Alert_To IS NULL and @Approval_Code = 'OFFER_LETTER'

							 
							/*-----------------------------------------------------------------------------------------------------------------*/		
						)tb
						order by [Ord]
		 
					END
  
	
		END	  



		--temp
		--select *from #Temp_Approver_1_Offer_Contract
		-- select *from #All_Data_Offer_Contract 
				select *,ROW_NUMBER() OVER(ORDER BY Email_Addr)[Orders],''[Addressee_Type] into #Distinct_Email_Addr_Temp_Offer_Contract
				from 
				(
						SELECT DISTINCT   Email_Addr       
						FROM #All_Data_Offer_Contract 
				)tb  
				---------------

				----------------------------------------- select *  	FROM #All_Data_Offer_Contract 
					DECLARE @Cnt_Offer_Contract int =1;
					SET  @Cnt_Offer_Contract =1;
					DECLARE @Cnt_Offer_ContractMAX int = 0;
					SELECT @Cnt_Offer_ContractMAX = COUNT(0) FROM #Distinct_Email_Addr_Temp_Offer_Contract;
					WHILE (@Cnt_Offer_Contract<=@Cnt_Offer_ContractMAX)
					BEGIN
						--DECLARE @TmpEmail_Addr varchar(100)='';
						set @TmpEmail_Addr ='';

						SELECT  @TmpEmail_Addr= Email_Addr from  #Distinct_Email_Addr_Temp_Offer_Contract where Orders=@Cnt_Offer_Contract;		 		  
						--Declare @Send_Multi_Types  Varchar(7000)='';     									 
						set @Send_Multi_Types   =null;

						Select 			         			
						@Send_Multi_Types = Coalesce( @Send_Multi_Types +  cast(Addressee_Type as varchar(100)),
						cast(Addressee_Type as varchar(100)) ) + ','  					
			 			
						from 
						(	 
							select  Addressee_Type
							from  #All_Data_Offer_Contract  where Email_Addr = @TmpEmail_Addr
						)tb
			
						SET @Send_Multi_Types = SUBSTRING(@Send_Multi_Types,0,LEN(@Send_Multi_Types)-0)		
						--Select @Send_Multi_Types,@TmpEmail_Addr;

						IF(LEN(@Send_Multi_Types)>1)
						BEGIN 

							 IF ( CHARINDEX('T',@Send_Multi_Types) > 0 )			    
							 BEGIN
									UPDATE #Distinct_Email_Addr_Temp_Offer_Contract set [Addressee_Type]='T' 
									WHERE  Orders = @Cnt_Offer_Contract;	
							 END
							 ELSE IF (CHARINDEX('C',@Send_Multi_Types) > 0 )
							 BEGIN
									UPDATE #Distinct_Email_Addr_Temp_Offer_Contract set [Addressee_Type]='C' 
									WHERE  Orders = @Cnt_Offer_Contract;	
							 END	
							 ELSE IF (CHARINDEX('B',@Send_Multi_Types) > 0 )
							 BEGIN
									update #Distinct_Email_Addr_Temp_Offer_Contract set [Addressee_Type]='B' 
									WHERE  Orders=@Cnt_Offer_Contract;	
							 END			 
						END
						ELSE
						BEGIN
							UPDATE #Distinct_Email_Addr_Temp_Offer_Contract set [Addressee_Type]=@Send_Multi_Types 
							WHERE  Orders=@Cnt_Offer_Contract;	
						END
						SET @Cnt_Offer_Contract= @Cnt_Offer_Contract+1; 
						SET @Send_Multi_Types = '';
						SET @TmpEmail_Addr =''
					END; 


			   SELECT 
					 @strTo_Recipients  = coalesce(@strTo_Recipients + Email_Addr , Email_Addr ) + ';'
			   From #Distinct_Email_Addr_Temp_Offer_Contract   Where  Addressee_Type = 'T'; 
			   SELECT  
					@strCc_Recipients  =  coalesce(@strCc_Recipients + Email_Addr , Email_Addr ) + ';'
			   From #Distinct_Email_Addr_Temp_Offer_Contract   Where  Addressee_Type = 'C';
			   SELECT 
					 @strBcc_Recipients  = coalesce(@strBcc_Recipients + Email_Addr , Email_Addr ) + ';'
			   From #Distinct_Email_Addr_Temp_Offer_Contract   Where  Addressee_Type = 'B';

			   SELECT @strTo_Recipients,@strCc_Recipients,@strBcc_Recipients
			     
				IF ( @strTo_Recipients is null )
				begin
					set @Error_Message ='E-Mail To address in not defined (Approver 1 is not present)..'
				end

			----------------------- SELECT *FROM  #Distinct_Email_Addr_Temp_Offer_Contract	
			DROP table #Distinct_Email_Addr_Temp_Offer_Contract;
			DROP table #All_Data_Offer_Contract ;
			DROP table #Temp_Approver_1_Offer_Contract;
			--DROP table #Temp_Approver_2;


END



ELSE IF (@Record_Status ='Get_Email_Ids_GRN')

BEGIN
	 
		CREATE TABLE #GRN_All_Data ([Ord] int,Email_Addr varchar(300),Types  varchar(300),Addressee_Type varchar(300))
		/*--------------------------------------------------------------------------------------------------------------------*/
		/*For level 1 : only the RIG is considered*/
		SELECT  
			1 [Ord],	dbo.Fnc_Get_Col_Value('dbo.Mst_User',Approver_User_Id,'EMAIl')Email_Addr,
			'APPROVER_1'[Type] ,'C' [Addressee_Type] 
			into #GRN_Temp_Approver_1 from  eos.Approver_Mapping map 
			INNER JOIN eos.Approval_Code cod on  map.Approval_Code_Id=cod.Approval_Code_Id
			INNER JOIN  eos.Approver_Mapping_Dtl mapApprover  on mapApprover.Approver_Mapping_Id = map.Approver_Mapping_Id
		WHERE Approver_Level= 1 
		AND Approver_Active= 'Y' AND Approval_Active ='Y' and Approval_Code = @Approval_Code   
		AND Receive_Mail = 'Y' 
		AND Dept_Id is null 
		AND Rig_Id = @Rig_Id  
	 
			/*
		    	Alert_Ids
		 
			  222	Material Requisition : Creation Mail 
			 
			*/ 						
			INSERT INTO #GRN_All_Data 
			SELECT * FROM 
			(     		
				 
				/*Logged in User*/
				SELECT  -1 [Ord] ,
				dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIl')Email_Addr,
				'Cur_Logged_In_User'[TYPE],'C' [Addressee_Type]				
				UNION				   
				SELECT  ROW_NUMBER() OVER(ORDER BY Mail_Alert_To_User_Id) ,
						RTRIM(LTRIM(Email_Addr))Email_Addr,'DataBase',Addressee_Type  FROM dbo.Mail_Alert_To_User 
					WHERE Alert_Id = 222  AND Mail_Alert_To IS NULL AND @Approval_Code = 'GRN'	
					
					UNION
					   SELECT  -2 [Ord] ,
					dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIL'),'GRN_Created_By','T' [Addressee_Type]
					from eos.GRN_Hdr WHERE  Grn_Hdr_Id = @Grn_Hdr_Id
					
									  
			/*----------------------------------------------MR and SR both----------------------------------------------------*/		
			   UNION
					/*Employees added in alert table  MATERIAL*/
					SELECT ROW_NUMBER() OVER(ORDER BY Addressee_Type) 
					  ,Email_Addr ,TYPE,'C' Addressee_Type FROM #GRN_Temp_Approver_1 		 
			/*-----------------------------------------------------------------------------------------------------------------*/		
			)tb
			ORDER BY [Ord]
		 		 
				select *, ROW_NUMBER() OVER(ORDER BY Email_Addr)[Orders],''[Addressee_Type] into #GRN_Distinct_Email_Addr_Temp
				from 
				( 
						SELECT DISTINCT top 1000
						Email_Addr from #GRN_All_Data  
				)tb 
				 
		  
				    -- DECLARE @Cnt int =1;
					SET  @Cnt =1;
					--DECLARE @CntMAX int = 0;
					set @CntMAX  =0;
					SELECT @CntMAX = COUNT(0) FROM #GRN_Distinct_Email_Addr_Temp;
					WHILE (@Cnt<=@CntMAX)
					BEGIN
					--DECLARE @TmpEmail_Addr varchar(100)='';
					set @TmpEmail_Addr=''
						SELECT  @TmpEmail_Addr= Email_Addr from  #GRN_Distinct_Email_Addr_Temp where Orders=@Cnt;		 		  
						--Declare @Send_Multi_Types  Varchar(7000)='';     									 
						set @Send_Multi_Types =''
						Select 			         			
						@Send_Multi_Types = Coalesce( @Send_Multi_Types +  cast(Addressee_Type as varchar(100)),
						cast(Addressee_Type as varchar(100)) ) + ','  					
			 			
						from 
						(	 
							select  Addressee_Type
							from  #GRN_All_Data  where Email_Addr = @TmpEmail_Addr
						)tb
			
						SET @Send_Multi_Types = SUBSTRING(@Send_Multi_Types,0,LEN(@Send_Multi_Types)-0)		
						--Select @Send_Multi_Types,@TmpEmail_Addr;

						IF(LEN(@Send_Multi_Types)>1)
						BEGIN 

							 IF ( CHARINDEX('T',@Send_Multi_Types) > 0 )			    
							 BEGIN
									UPDATE #GRN_Distinct_Email_Addr_Temp set [Addressee_Type]='T' 
									WHERE  Orders=@Cnt;	
							 END
							 ELSE IF (CHARINDEX('C',@Send_Multi_Types) > 0 )
							 BEGIN
									UPDATE #GRN_Distinct_Email_Addr_Temp set [Addressee_Type]='C' 
									WHERE  Orders=@Cnt;	
							 END	
							 ELSE IF (CHARINDEX('B',@Send_Multi_Types) > 0 )
							 BEGIN
									update #GRN_Distinct_Email_Addr_Temp set [Addressee_Type]='B' 
									WHERE  Orders=@Cnt;	
							 END			 
						END
						ELSE
						BEGIN
							UPDATE #GRN_Distinct_Email_Addr_Temp set [Addressee_Type]=@Send_Multi_Types 
							WHERE  Orders=@Cnt;	
						END
						SET @Cnt= @Cnt+1; 
						SET @Send_Multi_Types = '';
						SET @TmpEmail_Addr =''
					END; 

					 
			   SELECT 
					 @strTo_Recipients  = coalesce(@strTo_Recipients + Email_Addr , Email_Addr ) + ';'
			   From #GRN_Distinct_Email_Addr_Temp   Where  Addressee_Type = 'T'; 
			   SELECT  
					@strCc_Recipients  =  coalesce(@strCc_Recipients + Email_Addr , Email_Addr ) + ';'
			   From #GRN_Distinct_Email_Addr_Temp   Where  Addressee_Type = 'C';
			   SELECT 
					 @strBcc_Recipients  = coalesce(@strBcc_Recipients + Email_Addr , Email_Addr ) + ';'
			   From #GRN_Distinct_Email_Addr_Temp   Where  Addressee_Type = 'B';

			   SELECT @strTo_Recipients,@strCc_Recipients,@strBcc_Recipients
			     
				IF ( @strTo_Recipients is null )
				begin
					set @Error_Message ='E-Mail To address in not defined..'
				end
		 
			DROP table #GRN_Distinct_Email_Addr_Temp;
			DROP table #GRN_All_Data ;
			DROP table #GRN_Temp_Approver_1;
END
 


ELSE IF (@Record_Status ='Get_Email_Ids_Rig_Imprest')

BEGIN
	 
		CREATE TABLE #Rig_ImprestAll_Data ([Ord] int,Email_Addr varchar(300),Types  varchar(300),Addressee_Type varchar(300))
		/*--------------------------------------------------------------------------------------------------------------------*/
		/*For level 1 : only the RIG is considered*/
		SELECT  
			1 [Ord],	dbo.Fnc_Get_Col_Value('dbo.Mst_User',Approver_User_Id,'EMAIl')Email_Addr,
			'APPROVER_1'[Type] ,'C' [Addressee_Type] 
			into #Rig_ImprestTemp_Approver_1 from  eos.Approver_Mapping map 
			INNER JOIN eos.Approval_Code cod on  map.Approval_Code_Id=cod.Approval_Code_Id
			INNER JOIN  eos.Approver_Mapping_Dtl mapApprover  on mapApprover.Approver_Mapping_Id = map.Approver_Mapping_Id
		WHERE Approver_Level= 1 
		AND Approver_Active= 'Y' AND Approval_Active ='Y' and Approval_Code = @Approval_Code   
		AND Receive_Mail = 'Y' 
		AND Dept_Id is null 
		AND Rig_Id = @Rig_Id  
	 
			/*
		    	Alert_Ids
		 
			  //if in ffuture need to andd any common user then add alertid
			 
			*/ 						
	
		if(@Event_Type ='REVISE')
		begin
			INSERT INTO #Rig_ImprestAll_Data 
			SELECT * FROM 
			(     		
				 
				/*Logged in User*/
				SELECT  -1 [Ord] ,
				dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIl')Email_Addr,
				'Cur_Logged_In_User'[TYPE],'C' [Addressee_Type]				
				UNION	
						
			   SELECT  2 [Ord] ,
					dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIL'),'Rig_Imprest_Created_By','T' [Addressee_Type]
					from eos.OPC_Rig_Imprest WHERE  Rig_Imprest_Id = @Rig_Imprest_Id
				--change this in future if any comon user have to revise infor of Rig imprest
				--SELECT  ROW_NUMBER() OVER(ORDER BY Mail_Alert_To_User_Id) ,
				--		RTRIM(LTRIM(Email_Addr))Email_Addr,'DataBase',Addressee_Type  FROM 
				--		dbo.Mail_Alert_To_User 
				--	WHERE Alert_Id = 222  AND Mail_Alert_To IS NULL AND @Approval_Code = 'GRN'					  
			/*----------------------------------------------MR and SR both----------------------------------------------------*/		
			   UNION
					/*Employees added in alert table  MATERIAL*/
					SELECT ROW_NUMBER() OVER(ORDER BY Addressee_Type) 
					  ,Email_Addr ,TYPE,'C' Addressee_Type FROM #Rig_ImprestTemp_Approver_1 		 
			/*-----------------------------------------------------------------------------------------------------------------*/		
			)tb
			ORDER BY [Ord]
		 end		 
				select *, ROW_NUMBER() OVER(ORDER BY Email_Addr)[Orders],''[Addressee_Type] into #Rig_ImprestDistinct_Email_Addr_Temp
				from 
				( 
						SELECT DISTINCT top 1000
						Email_Addr from #Rig_ImprestAll_Data  
				)tb 
				 
		  
				    -- DECLARE @Cnt int =1;
					SET  @Cnt =1;
					--DECLARE @CntMAX int = 0;
					set @CntMAX  =0;
					SELECT @CntMAX = COUNT(0) FROM #Rig_ImprestDistinct_Email_Addr_Temp;
					WHILE (@Cnt<=@CntMAX)
					BEGIN
					--DECLARE @TmpEmail_Addr varchar(100)='';
					set @TmpEmail_Addr=''
						SELECT  @TmpEmail_Addr= Email_Addr from  #Rig_ImprestDistinct_Email_Addr_Temp where Orders=@Cnt;		 		  
						--Declare @Send_Multi_Types  Varchar(7000)='';     									 
						set @Send_Multi_Types =''
						Select 			         			
						@Send_Multi_Types = Coalesce( @Send_Multi_Types +  cast(Addressee_Type as varchar(100)),
						cast(Addressee_Type as varchar(100)) ) + ','  					
			 			
						from 
						(	 
							select  Addressee_Type
							from  #Rig_ImprestAll_Data  where Email_Addr = @TmpEmail_Addr
						)tb
			
						SET @Send_Multi_Types = SUBSTRING(@Send_Multi_Types,0,LEN(@Send_Multi_Types)-0)		
						--Select @Send_Multi_Types,@TmpEmail_Addr;

						IF(LEN(@Send_Multi_Types)>1)
						BEGIN 

							 IF ( CHARINDEX('T',@Send_Multi_Types) > 0 )			    
							 BEGIN
									UPDATE #Rig_ImprestDistinct_Email_Addr_Temp set [Addressee_Type]='T' 
									WHERE  Orders=@Cnt;	
							 END
							 ELSE IF (CHARINDEX('C',@Send_Multi_Types) > 0 )
							 BEGIN
									UPDATE #Rig_ImprestDistinct_Email_Addr_Temp set [Addressee_Type]='C' 
									WHERE  Orders=@Cnt;	
							 END	
							 ELSE IF (CHARINDEX('B',@Send_Multi_Types) > 0 )
							 BEGIN
									update #Rig_ImprestDistinct_Email_Addr_Temp set [Addressee_Type]='B' 
									WHERE  Orders=@Cnt;	
							 END			 
						END
						ELSE
						BEGIN
							UPDATE #Rig_ImprestDistinct_Email_Addr_Temp set [Addressee_Type]=@Send_Multi_Types 
							WHERE  Orders=@Cnt;	
						END
						SET @Cnt= @Cnt+1; 
						SET @Send_Multi_Types = '';
						SET @TmpEmail_Addr =''
					END; 

					 
			   SELECT 
					 @strTo_Recipients  = coalesce(@strTo_Recipients + Email_Addr , Email_Addr ) + ';'
			   From #Rig_ImprestDistinct_Email_Addr_Temp   Where  Addressee_Type = 'T'; 
			   SELECT  
					@strCc_Recipients  =  coalesce(@strCc_Recipients + Email_Addr , Email_Addr ) + ';'
			   From #Rig_ImprestDistinct_Email_Addr_Temp   Where  Addressee_Type = 'C';
			   SELECT 
					 @strBcc_Recipients  = coalesce(@strBcc_Recipients + Email_Addr , Email_Addr ) + ';'
			   From #Rig_ImprestDistinct_Email_Addr_Temp   Where  Addressee_Type = 'B';

			   SELECT @strTo_Recipients,@strCc_Recipients,@strBcc_Recipients
			     
				IF ( @strTo_Recipients is null )
				begin
					set @Error_Message ='E-Mail To address in not defined..'
				end
		 
			DROP table #Rig_ImprestDistinct_Email_Addr_Temp;
			DROP table #Rig_ImprestAll_Data ;
			DROP table #Rig_ImprestTemp_Approver_1;
END
 
ELSE IF (@Record_Status ='Get_Email_Ids_Material_Cost')

BEGIN
	 
		CREATE TABLE #Material_Cost_All_Data ([Ord] int,Email_Addr varchar(300),Types  varchar(300),Addressee_Type varchar(300))
		/*--------------------------------------------------------------------------------------------------------------------*/
		/*For level 1 : only the RIG is considered*/
		SELECT  
			1 [Ord],	dbo.Fnc_Get_Col_Value('dbo.Mst_User',Approver_User_Id,'EMAIl')Email_Addr,
			'APPROVER_1'[Type] ,'C' [Addressee_Type] 
			into #Material_Cost_Temp_Approver_1 from  eos.Approver_Mapping map 
			INNER JOIN eos.Approval_Code cod on  map.Approval_Code_Id=cod.Approval_Code_Id
			INNER JOIN  eos.Approver_Mapping_Dtl mapApprover  on mapApprover.Approver_Mapping_Id = map.Approver_Mapping_Id
		WHERE Approver_Level= 1 
		AND Approver_Active= 'Y' AND Approval_Active ='Y' and Approval_Code = @Approval_Code   
		AND Receive_Mail = 'Y' 
		AND Dept_Id is null 
		AND Rig_Id = @Rig_Id  
	 
			/*
		    	Alert_Ids
		 
			  //if in ffuture need to andd any common user then add alertid
			 
			*/ 						
	
		if(@Event_Type ='REVISE')
		begin
			INSERT INTO #Material_Cost_All_Data 
			SELECT * FROM 
			(     		
				 
				/*Logged in User*/
				SELECT  -1 [Ord] ,
				dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIl')Email_Addr,
				'Cur_Logged_In_User'[TYPE],'C' [Addressee_Type]				
				UNION	
						
			   SELECT  2 [Ord] ,
					dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIL'),'Rig_Imprest_Created_By','T' [Addressee_Type]
					from eos.OPC_Material_Cost WHERE  Material_Cost_Id = @Material_Cost_Id 
				--change this in future if any comon user have to revise infor of Rig imprest
				--SELECT  ROW_NUMBER() OVER(ORDER BY Mail_Alert_To_User_Id) ,
				--		RTRIM(LTRIM(Email_Addr))Email_Addr,'DataBase',Addressee_Type  FROM 
				--		dbo.Mail_Alert_To_User 
				--	WHERE Alert_Id = 222  AND Mail_Alert_To IS NULL AND @Approval_Code = 'GRN'					  
			/*----------------------------------------------MR and SR both----------------------------------------------------*/		
			   UNION
					/*Employees added in alert table  MATERIAL*/
					SELECT ROW_NUMBER() OVER(ORDER BY Addressee_Type) 
					  ,Email_Addr ,TYPE,'C' Addressee_Type FROM #Material_Cost_Temp_Approver_1 		 
			/*-----------------------------------------------------------------------------------------------------------------*/		
			)tb
			ORDER BY [Ord]
		 end		 
				select *, ROW_NUMBER() OVER(ORDER BY Email_Addr)[Orders],''[Addressee_Type] into #Material_Cost_Distinct_Email_Addr_Temp
				from 
				( 
						SELECT DISTINCT top 1000
						Email_Addr from #Material_Cost_All_Data  
				)tb 
				 
		  
				    -- DECLARE @Cnt int =1;
					SET  @Cnt =1;
					--DECLARE @CntMAX int = 0;
					set @CntMAX  =0;
					SELECT @CntMAX = COUNT(0) FROM #Material_Cost_Distinct_Email_Addr_Temp;
					WHILE (@Cnt<=@CntMAX)
					BEGIN
					--DECLARE @TmpEmail_Addr varchar(100)='';
					set @TmpEmail_Addr=''
						SELECT  @TmpEmail_Addr= Email_Addr from  #Material_Cost_Distinct_Email_Addr_Temp where Orders=@Cnt;		 		  
						--Declare @Send_Multi_Types  Varchar(7000)='';     									 
						set @Send_Multi_Types =''
						Select 			         			
						@Send_Multi_Types = Coalesce( @Send_Multi_Types +  cast(Addressee_Type as varchar(100)),
						cast(Addressee_Type as varchar(100)) ) + ','  					
			 			
						from 
						(	 
							select  Addressee_Type
							from  #Material_Cost_All_Data  where Email_Addr = @TmpEmail_Addr
						)tb
			
						SET @Send_Multi_Types = SUBSTRING(@Send_Multi_Types,0,LEN(@Send_Multi_Types)-0)		
						--Select @Send_Multi_Types,@TmpEmail_Addr;

						IF(LEN(@Send_Multi_Types)>1)
						BEGIN 

							 IF ( CHARINDEX('T',@Send_Multi_Types) > 0 )			    
							 BEGIN
									UPDATE #Material_Cost_Distinct_Email_Addr_Temp set [Addressee_Type]='T' 
									WHERE  Orders=@Cnt;	
							 END
							 ELSE IF (CHARINDEX('C',@Send_Multi_Types) > 0 )
							 BEGIN
									UPDATE #Material_Cost_Distinct_Email_Addr_Temp set [Addressee_Type]='C' 
									WHERE  Orders=@Cnt;	
							 END	
							 ELSE IF (CHARINDEX('B',@Send_Multi_Types) > 0 )
							 BEGIN
									update #Material_Cost_Distinct_Email_Addr_Temp set [Addressee_Type]='B' 
									WHERE  Orders=@Cnt;	
							 END			 
						END
						ELSE
						BEGIN
							UPDATE #Material_Cost_Distinct_Email_Addr_Temp set [Addressee_Type]=@Send_Multi_Types 
							WHERE  Orders=@Cnt;	
						END
						SET @Cnt= @Cnt+1; 
						SET @Send_Multi_Types = '';
						SET @TmpEmail_Addr =''
					END; 

					 
			   SELECT 
					 @strTo_Recipients  = coalesce(@strTo_Recipients + Email_Addr , Email_Addr ) + ';'
			   From #Material_Cost_Distinct_Email_Addr_Temp   Where  Addressee_Type = 'T'; 
			   SELECT  
					@strCc_Recipients  =  coalesce(@strCc_Recipients + Email_Addr , Email_Addr ) + ';'
			   From #Material_Cost_Distinct_Email_Addr_Temp   Where  Addressee_Type = 'C';
			   SELECT 
					 @strBcc_Recipients  = coalesce(@strBcc_Recipients + Email_Addr , Email_Addr ) + ';'
			   From #Material_Cost_Distinct_Email_Addr_Temp   Where  Addressee_Type = 'B';

			   SELECT @strTo_Recipients,@strCc_Recipients,@strBcc_Recipients
			     
				IF ( @strTo_Recipients is null )
				begin
					set @Error_Message ='E-Mail To address in not defined..'
				end
		 
			DROP table #Material_Cost_Distinct_Email_Addr_Temp;
			DROP table #Material_Cost_All_Data ;
			DROP table #Material_Cost_Temp_Approver_1;
END
 




ELSE IF (@Record_Status ='Get_Email_Ids_Invoice_Hdr')
BEGIN
	 
		CREATE TABLE #Invoice_hdr_All_Data ([Ord] int,Email_Addr varchar(300),Types  varchar(300),Addressee_Type varchar(300))
		/*--------------------------------------------------------------------------------------------------------------------*/
		/*For level 1 : only the RIG is considered*/
		SELECT  
			1 [Ord],	dbo.Fnc_Get_Col_Value('dbo.Mst_User',Approver_User_Id,'EMAIl')Email_Addr,
			'APPROVER_1'[Type] ,'C' [Addressee_Type] 
			into #Invoice_hdr_Temp_Approver_1 from  eos.Approver_Mapping map 
			INNER JOIN eos.Approval_Code cod on  map.Approval_Code_Id=cod.Approval_Code_Id
			INNER JOIN  eos.Approver_Mapping_Dtl mapApprover  on mapApprover.Approver_Mapping_Id = map.Approver_Mapping_Id
		WHERE Approver_Level= 1 
		and Approver_Active= 'Y' and Approval_Active ='Y' and Approval_Code = @Approval_Code and 
		((@DB_USER_TYPE  ='CREATOR' AND 1=1) OR  (@DB_USER_TYPE <> 'CREATOR' AND Receive_Mail = 'Y'))/*this can be MR_ON or SR_ON*/
		--and Dept_Id is null 
		and Rig_Id = @Rig_Id 
		
		/*For level 2 : RIG and DEPARTMENT is considered*/
		SELECT  
			1 [Ord],	dbo.Fnc_Get_Col_Value('dbo.Mst_User',Approver_User_Id,'EMAIl')Email_Addr,
			'APPROVER_2'[Type] ,'C' [Addressee_Type] 
			into #Invoice_hdr_Temp_Approver_2 from  eos.Approver_Mapping map 
			INNER JOIN eos.Approval_Code cod on  map.Approval_Code_Id=cod.Approval_Code_Id
			INNER JOIN  eos.Approver_Mapping_Dtl mapApprover  on mapApprover.Approver_Mapping_Id = map.Approver_Mapping_Id
		WHERE Approver_Level= 2 
		AND Approver_Active= 'Y' AND Approval_Active ='Y' AND Approval_Code = @Approval_Code   and 
		
		((@DB_USER_TYPE  ='CREATOR' AND Receive_Mail = 'Y') OR ( @DB_USER_TYPE <> 'CREATOR' AND Receive_Mail = 'Y'))/*this can be MR_ON or SR_ON*/
		--AND Dept_Id = @Dept_Id  
		AND Rig_Id = @Rig_Id


		SELECT  
			1 [Ord],	dbo.Fnc_Get_Col_Value('dbo.Mst_User',Approver_User_Id,'EMAIl')Email_Addr,
			'APPROVER_1'[Type] ,'C' [Addressee_Type] 
			into #Invoice_hdr_Temp_Approver_3 from  eos.Approver_Mapping map 
			INNER JOIN eos.Approval_Code cod on  map.Approval_Code_Id=cod.Approval_Code_Id
			INNER JOIN  eos.Approver_Mapping_Dtl mapApprover  on mapApprover.Approver_Mapping_Id = map.Approver_Mapping_Id
		WHERE Approver_Level= 3 
		and Approver_Active= 'Y' and Approval_Active ='Y' and Approval_Code = @Approval_Code and 
		((@DB_USER_TYPE  ='CREATOR' AND 1=1) OR  (@DB_USER_TYPE <> 'CREATOR' AND Receive_Mail = 'Y'))/*this can be MR_ON or SR_ON*/
		--and Dept_Id is null 
		and Rig_Id = @Rig_Id 
		 
		 
		 /*--------------------------------------------------------------------------------------------------------------------*/
			

				
		if(@Event_Type ='INSERT')
		BEGIN
					IF(@DB_USER_TYPE  ='CREATOR')
					BEGIN
						  
						
							INSERT INTO #Invoice_hdr_All_Data 

							SELECT * FROM 
							(       /*Approver level 1*/
				 
									SELECT  1[Ord]  ,Email_Addr ,TYPE,'T' Addressee_Type FROM #Invoice_hdr_Temp_Approver_1
							UNION 
								   /*Logged in User*/
									SELECT  2 [Ord] ,
									dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIl'),
									'Cur_Logged_In_User','C' [Addressee_Type]


							UNION
								 
									SELECT  3 [Ord],
									 RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type  FROM dbo.Mail_Alert_To_User 
									WHERE Alert_Id = 229  AND Mail_Alert_To IS NULL AND @Approval_Code = 'INVOICE_HDR'

							UNION
								  /*Employees common added in Rig email mapping*/
									SELECT 4 [Ord],
							dbo.Fnc_Get_Col_Value('dbo.Mst_User',User_Id,'EMAIL') User_Email ,'Mapping','C'
									From eos.Rig_To_Email_Mapping  
									Where Alert_Id = 229 
									AND Rig_Id = @Rig_Id
									--And Addressee_Type = 'T'
									AND To_Dt IS NULL 
						/*-----------------------------------------------------------------------------------------------------------------*/		
						)tb
						ORDER BY [Ord]
		 
					END

					IF(@DB_USER_TYPE  ='APPROVER_1')
					BEGIN
					     
									INSERT INTO #Invoice_hdr_All_Data 
									SELECT * FROM   
									(       /*Approver level 1*/
										 SELECT [Ord]  ,Email_Addr ,Type,'T' Addressee_Type From #Invoice_hdr_Temp_Approver_2
								
										 UNION
		
										 SELECT  2 [Ord] ,
											dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIL'),'Invoice_Created_By','C' [Addressee_Type]
											from eos.Invoice_Hdr WHERE Invoice_Hdr_Id = @Invoice_Hdr_Id 
										 UNION 
											/*Logged in User*/
											SELECT  3 [Ord] ,
											dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIL'),'Cur_Logged_In_User','C' [Addressee_Type]

										 /*----------------------------------------------MR and SR both----------------------------------------------------*/	
										 UNION
											/*Employees added in alert table MATERIAL*/
											SELECT  4 [Ord],
											RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type  FROM dbo.Mail_Alert_To_User 
											Where Alert_Id = 229  AND Mail_Alert_To IS NULL and @Approval_Code = 'INVOICE_HDR'
										UNION
										  /*Employees common added in Rig email mapping*/
											SELECT 5 [Ord],
												dbo.Fnc_Get_Col_Value('dbo.Mst_User',User_Id,'EMAIL') User_Email,'MAPPING' ,'C'
											From eos.Rig_To_Email_Mapping  
											Where Alert_Id = 229 
											AND Rig_Id = @Rig_Id
											--And Addressee_Type = 'T'
											AND To_Dt IS NULL 
							 /*-----------------------------------------------------------------------------------------------------------------*/		
									)tb
									order by [Ord]
						 
					END
 
             end
		if(@Event_Type ='FINALIZE')
		BEGIN
					IF(@DB_USER_TYPE  ='CREATOR')
					BEGIN
						  
						
							INSERT INTO #Invoice_hdr_All_Data 

							SELECT * FROM 
							(       /*Approver level 1*/
				 
									SELECT  1[Ord]  ,Email_Addr ,TYPE,'T' Addressee_Type FROM #Invoice_hdr_Temp_Approver_1
							UNION 
								   /*Logged in User*/
									SELECT  2 [Ord] ,
									dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIl'),'Cur_Logged_In_User','C' [Addressee_Type]


							UNION
								 
									SELECT  3 [Ord],
									 RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type  FROM dbo.Mail_Alert_To_User 
									WHERE Alert_Id = 229  AND Mail_Alert_To IS NULL AND @Approval_Code = 'INVOICE_HDR'

							UNION
								  /*Employees common added in Rig email mapping*/
									SELECT 4 [Ord],
							dbo.Fnc_Get_Col_Value('dbo.Mst_User',User_Id,'EMAIL') User_Email ,'MAPPING','C'
									From eos.Rig_To_Email_Mapping  
									Where Alert_Id = 229 
									AND Rig_Id = @Rig_Id
									--And Addressee_Type = 'T'
									AND To_Dt IS NULL 
						/*-----------------------------------------------------------------------------------------------------------------*/		
						)tb
						ORDER BY [Ord]
		 
					END

					IF(@DB_USER_TYPE  ='APPROVER_1')
					BEGIN
					     IF(@DB_USER_TYPE_Approval_Status ='A') 
						 BEGIN
									INSERT INTO #Invoice_hdr_All_Data 
									SELECT * FROM   
									(       /*Approver level 1*/
										 SELECT 1 [Ord]  ,Email_Addr ,Type,'T' Addressee_Type From #Invoice_hdr_Temp_Approver_2
								
										 UNION
		
										 SELECT  2 [Ord] ,
											dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIL'),'Invoice_Created_By','C' [Addressee_Type]
											from eos.Invoice_Hdr WHERE Invoice_Hdr_Id = @Invoice_Hdr_Id

						 
										/*-----------------------------------------------------------------------------------------------------------------*/		
										 UNION 
											/*Logged in User*/
											SELECT  3 [Ord] ,
											dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIL'),'Cur_Logged_In_User','C' [Addressee_Type]

										 /*----------------------------------------------MR and SR both----------------------------------------------------*/	
										 UNION
											/*Employees added in alert table MATERIAL*/
											SELECT  4 [Ord],
											RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type  FROM dbo.Mail_Alert_To_User 
											Where Alert_Id = 229  AND Mail_Alert_To IS NULL and @Approval_Code = 'INVOICE_HDR'
										UNION
										  /*Employees common added in Rig email mapping*/
											SELECT 5 [Ord],
												dbo.Fnc_Get_Col_Value('dbo.Mst_User',User_Id,'EMAIL') User_Email,'MAPPING' ,'C'
											From eos.Rig_To_Email_Mapping  
											Where Alert_Id = 229 
											AND Rig_Id = @Rig_Id
											--And Addressee_Type = 'T'
											AND To_Dt IS NULL 
							 /*-----------------------------------------------------------------------------------------------------------------*/		
									)tb
									order by [Ord]
						end
		 			     
						 else IF(@DB_USER_TYPE_Approval_Status ='R') 
						 BEGIN
									INSERT INTO #Invoice_hdr_All_Data 
									SELECT * FROM   
									(       

		
										 SELECT  1 [Ord] ,
											dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIL')Email_Addr,
											'Invoice_Created_By'[Type], 'T' Addressee_Type
											from eos.Invoice_Hdr WHERE Invoice_Hdr_Id = @Invoice_Hdr_Id

						 
										/*-----------------------------------------------------------------------------------------------------------------*/		
										 UNION 
											/*Logged in User*/
											SELECT  2 [Ord] ,
											dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIL'),
											
											'Cur_Logged_In_User','C' [Addressee_Type]

										 /*-------------------------------------------------------*/	
										 UNION
											/*Employees added in alert table MATERIAL*/
											SELECT  3 [Ord],
											RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type  FROM dbo.Mail_Alert_To_User 
											Where Alert_Id = 229  AND Mail_Alert_To IS NULL and @Approval_Code = 'INVOICE_HDR'
										UNION
										  /*Employees common added in Rig email mapping*/
											SELECT 4 [Ord],
												dbo.Fnc_Get_Col_Value('dbo.Mst_User',User_Id,'EMAIL') User_Email, 'MAPPING' ,'C'
											From eos.Rig_To_Email_Mapping  
											Where Alert_Id = 229 
											AND Rig_Id = @Rig_Id
											--And Addressee_Type = 'T'
											AND To_Dt IS NULL 
							 /*-----------------------------------------------------------------------------------------------------------------*/		
									)tb
									order by [Ord]
						end
		 			     
					END
 
					IF(@DB_USER_TYPE  ='APPROVER_2')
					BEGIN
				         IF(@DB_USER_TYPE_Approval_Status ='A') 
						 BEGIN
									INSERT INTO #Invoice_hdr_All_Data 

									SELECT * FROM   
									(       /*Approver level 1*/
										SELECT 1 [Ord]  ,Email_Addr ,Type,'T' Addressee_Type From #Invoice_hdr_Temp_Approver_3
							
										/*----------------------------------------------MR and SR both----------------------------------------------------*/
										UNION		
											SELECT  2 [Ord] ,dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIL'),'Invoice_Created_By','C' [Addressee_Type]
											from eos.Invoice_Hdr where  Invoice_Hdr_Id = @Invoice_Hdr_Id
						 
										/*-----------------------------------------------------------------------------------------------------------------*/	
										UNION 
										   /*Logged in User*/
											SELECT  3 [Ord] ,dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIl'),'Cur_Logged_In_User','C' [Addressee_Type]

										 
										UNION
										  /*Employees added in alert table MATERIAL*/
											SELECT  4 [Ord],RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type From dbo.Mail_Alert_To_User 
											Where Alert_Id = 229  AND Mail_Alert_To IS NULL and @Approval_Code = 'INVOICE_HDR'

									   UNION
										  /*Employees common added in Rig email mapping*/
											SELECT 5 [Ord],
												dbo.Fnc_Get_Col_Value('dbo.Mst_User',User_Id,'EMAIL') User_Email ,'MAPPING' ,'C'
											From eos.Rig_To_Email_Mapping  
											Where Alert_Id = 229 
											AND Rig_Id = @Rig_Id
											--And Addressee_Type = 'T'
											AND To_Dt IS NULL 
										/*-----------------------------------------------------------------------------------------------------------------*/
									)tb
									order by [Ord]
							END
					     ELSE  IF(@DB_USER_TYPE_Approval_Status ='R') 
						 BEGIN
									INSERT INTO #Invoice_hdr_All_Data 

									SELECT * FROM   
									(       /*Approver level 1*/
										SELECT 1 [Ord]  ,Email_Addr ,Type,'T' Addressee_Type From #Invoice_hdr_Temp_Approver_1
							
										
										UNION		
											SELECT  2 [Ord] ,dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIL'),'Invoice_Created_By','C' [Addressee_Type]
											from eos.Invoice_Hdr where  Invoice_Hdr_Id = @Invoice_Hdr_Id
						 
										
										UNION 
										   /*Logged in User*/
											SELECT  3 [Ord] ,dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIl'),'Cur_Logged_In_User','C' [Addressee_Type]

										 
										UNION
										  /*Employees added in alert table MATERIAL*/
											SELECT  4 [Ord],RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type From dbo.Mail_Alert_To_User 
											Where Alert_Id = 229  AND Mail_Alert_To IS NULL and @Approval_Code = 'INVOICE_HDR'

									   UNION
										  /*Employees common added in Rig email mapping*/
											SELECT 5 [Ord],
												dbo.Fnc_Get_Col_Value('dbo.Mst_User',User_Id,'EMAIL') User_Email ,'MAPPING' ,'C'
											From eos.Rig_To_Email_Mapping  
											Where Alert_Id = 229 
											AND Rig_Id = @Rig_Id
											--And Addressee_Type = 'T'
											AND To_Dt IS NULL 
										/*-----------------------------------------------------------------------------------------------------------------*/
									)tb
									order by [Ord]
							END
					END   
		
					IF(@DB_USER_TYPE  ='APPROVER_3')
					BEGIN
					    IF(@DB_USER_TYPE_Approval_Status ='A') 
						 BEGIN
								INSERT INTO #Invoice_hdr_All_Data 

								SELECT * FROM   
								(       /*Approver level 1*/
									SELECT  1 [Ord]  ,Email_Addr ,Type,'T' Addressee_Type From #Invoice_hdr_Temp_Approver_1
									union
									SELECT 2 [Ord]  ,Email_Addr ,Type,'T' Addressee_Type From #Invoice_hdr_Temp_Approver_2
							
									/*--------------------------------------------- -------------------------------------------------*/
									UNION		
										SELECT 3 [Ord] ,dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIL'),'Invoice_Created_By','C' [Addressee_Type]
										from eos.Invoice_Hdr where  Invoice_Hdr_Id = @Invoice_Hdr_Id
						 
									/*-----------------------------------------------------------------------------------------------------------------*/	
									UNION 
									   /*Logged in User*/
										SELECT  4 [Ord] ,dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIl'),'Cur_Logged_In_User','C' [Addressee_Type]

									/*--------------------------------------------- ----------------------------------------------------*/							
									UNION
							  
										SELECT  5 [Ord],RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type From dbo.Mail_Alert_To_User 
										Where Alert_Id = 229  AND Mail_Alert_To IS NULL and @Approval_Code = 'INVOICE_HDR'

								   UNION
									  /*Employees common added in Rig email mapping*/
										SELECT 6 [Ord],
											dbo.Fnc_Get_Col_Value('dbo.Mst_User',User_Id,'EMAIL') User_Email ,'MAPPING' ,'C'
										From eos.Rig_To_Email_Mapping  
										Where Alert_Id = 229 
										AND Rig_Id = @Rig_Id
										--And Addressee_Type = 'T'
										AND To_Dt IS NULL 
									/*-----------------------------------------------------------------------------------------------------------------*/
								)tb
								order by [Ord]
							END
		                 ELSE IF(@DB_USER_TYPE_Approval_Status ='R') 
						 BEGIN
								INSERT INTO #Invoice_hdr_All_Data 

								SELECT * FROM   
								(        
									SELECT 1 [Ord]  ,Email_Addr ,Type,'T' Addressee_Type From #Invoice_hdr_Temp_Approver_1
							
									/*--------------------------------------------- -------------------------------------------------*/
									UNION		
										SELECT 2 [Ord] ,dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIL'),'Invoice_Created_By','C' [Addressee_Type]
										from eos.Invoice_Hdr where  Invoice_Hdr_Id = @Invoice_Hdr_Id
						 
									/*-----------------------------------------------------------------------------------------------------------------*/	
									UNION 
									   /*Logged in User*/
										SELECT  3 [Ord] ,dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIl'),'Cur_Logged_In_User','C' [Addressee_Type]

									/*--------------------------------------------- ----------------------------------------------------*/							
									UNION
							  
										SELECT  4 [Ord],RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type From dbo.Mail_Alert_To_User 
										Where Alert_Id = 229  AND Mail_Alert_To IS NULL and @Approval_Code = 'INVOICE_HDR'

								   UNION
									  /*Employees common added in Rig email mapping*/
										SELECT 5 [Ord],
											dbo.Fnc_Get_Col_Value('dbo.Mst_User',User_Id,'EMAIL') User_Email ,'MAPPING' ,'C'
										From eos.Rig_To_Email_Mapping  
										Where Alert_Id = 229 
										AND Rig_Id = @Rig_Id
										--And Addressee_Type = 'T'
										AND To_Dt IS NULL 
									/*-----------------------------------------------------------------------------------------------------------------*/
								)tb
								order by [Ord]
							END
					END 
		END	

			
		IF(@Event_Type ='REVISE')
		BEGIN
							IF(@DB_USER_TYPE  ='APPROVER_1')
							BEGIN
								 
								INSERT INTO #Invoice_hdr_All_Data 
								SELECT * FROM   
								(       
										 /*Approver level 1*/
										 SELECT [Ord], Email_Addr ,Type,'C' Addressee_Type FROM #Invoice_hdr_Temp_Approver_2
										
										 /*-------------------------------------------- --------------------------------------------------------------*/	
										 UNION												 
										 SELECT 2 [Ord], dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIl'),'Invoice_Created_By','T' [Addressee_Type]
										 FROM eos.Invoice_Hdr WHERE  Invoice_Hdr_Id = @Invoice_Hdr_Id										 
										 /*--------------------------------------------------------------------------------------------------------------------------*/	

										 UNION 
										 /*Logged in User*/
										 SELECT 3 [Ord], dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIl'),'Cur_Logged_In_User','C' [Addressee_Type]

										 /*----------------------------------------------MR and SR both--------------------------------------------------------------*/	
										 UNION
										 
										 SELECT 4 [Ord], RTRIM(LTRIM(Email_Addr)),'DataBase', Addressee_Type  FROM dbo.Mail_Alert_To_User 
										 WHERE Alert_Id = 229  AND Mail_Alert_To IS NULL AND @Approval_Code = 'INVOICE_HDR'
										  
										/*----------------------------------------------------------------------------------------------------------------------------*/	
									)tb
									ORDER BY [Ord];		 
								END
 
								IF(@DB_USER_TYPE  ='APPROVER_2')
								BEGIN
								 
									INSERT INTO #Invoice_hdr_All_Data 
									SELECT * FROM   
									(       /*Approver level 1*/
											/*--------------------------------------------------------------------------------------------------------------------------*/
											SELECT [Ord]  ,Email_Addr ,Type,'C' Addressee_Type From #Invoice_hdr_Temp_Approver_3
												
											/*----------------------------------------------MR and SR both--------------------------------------------------------------*/										
											UNION		 
											SELECT  2 [Ord] ,
											dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIl'),'MR_Created_By','T' [Addressee_Type]
											from eos.Invoice_Hdr WHERE  Invoice_Hdr_Id = @Invoice_Hdr_Id

										 
											/*--------------------------------------------------------------------------------------------------------------------------*/
											UNION 
											/*Logged in User*/
											SELECT  3 [Ord] ,
											dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIl'),'Cur_Logged_In_User','C' [Addressee_Type]
												
												
											UNION
											
											SELECT  4 [Ord],
											RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type  FROM dbo.Mail_Alert_To_User 
											Where Alert_Id = 229  AND Mail_Alert_To IS NULL AND @Approval_Code = 'MR_ON'
											
											 
											
									)tb
									ORDER BY [Ord]
		 
								END  
								
								
								
								iF(@DB_USER_TYPE  ='APPROVER_3')
								BEGIN
								 
									INSERT INTO #Invoice_hdr_All_Data 
									SELECT * FROM   
									(       /*Approver level 1*/
											/*--------------------------------------------------------------------------------------------------------------------------*/
											SELECT [Ord]  ,Email_Addr ,Type,'C' Addressee_Type From #Invoice_hdr_Temp_Approver_1
											UNION
											SELECT [Ord]  ,Email_Addr ,Type,'C' Addressee_Type From #Invoice_hdr_Temp_Approver_2
												
											/*-----------------------------------------------------------------------------------------------------*/										
											UNION		 
											SELECT 3 [Ord] ,
											dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIl'),'Invoice_Created_By','T' [Addressee_Type]
											from eos.Invoice_Hdr WHERE  Invoice_Hdr_Id = @Invoice_Hdr_Id

										 
											/*--------------------------------------------------------------------------------------------------------------------------*/
											UNION 
											/*Logged in User*/
											SELECT  3 [Ord] ,
											dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIl'),'Cur_Logged_In_User','C' [Addressee_Type]
												
												
											UNION										 
											SELECT  4 [Ord],
											RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type  FROM dbo.Mail_Alert_To_User 
											Where Alert_Id = 229  AND Mail_Alert_To IS NULL AND @Approval_Code = 'INVOICE_HDR'
																				 
											
									)tb
									ORDER BY [Ord]
		 
								END   
	
			 END;


			 
				select *,ROW_NUMBER() OVER(ORDER BY Email_Addr)[Orders],''[Addressee_Type] into #Invoice_hdr_Distinct_Email_Addr_Temp
				from 
				(
						SELECT DISTINCT   Email_Addr       
						FROM #Invoice_hdr_All_Data 
				)tb  
				---------------

				----------------------------------------- select *  	FROM #Invoice_hdr_All_Data 
					--DECLARE @Cnt int =1;
					SET  @Cnt =1;
					--DECLARE @CntMAX int = 0;
					set  @CntMAX =0;
					SELECT @CntMAX = COUNT(0) FROM #Invoice_hdr_Distinct_Email_Addr_Temp;
					WHILE (@Cnt<=@CntMAX)
					BEGIN
					  --DECLARE @TmpEmail_Addr varchar(100)='';
					  set  @TmpEmail_Addr ='';
						SELECT  @TmpEmail_Addr= Email_Addr from  #Invoice_hdr_Distinct_Email_Addr_Temp where Orders=@Cnt;		 		  
						--Declare @Send_Multi_Types  Varchar(7000)='';     									 
						set @Send_Multi_Types ='';
						Select 			         			
						@Send_Multi_Types = Coalesce( @Send_Multi_Types +  cast(Addressee_Type as varchar(100)),
						cast(Addressee_Type as varchar(100)) ) + ','  					
			 			
						from 
						(	 
							select  Addressee_Type
							from  #Invoice_hdr_All_Data  where Email_Addr = @TmpEmail_Addr
						)tb
			
						SET @Send_Multi_Types = SUBSTRING(@Send_Multi_Types,0,LEN(@Send_Multi_Types)-0)		
						--Select @Send_Multi_Types,@TmpEmail_Addr;

						IF(LEN(@Send_Multi_Types)>1)
						BEGIN 

							 IF ( CHARINDEX('T',@Send_Multi_Types) > 0 )			    
							 BEGIN
									UPDATE #Invoice_hdr_Distinct_Email_Addr_Temp set [Addressee_Type]='T' 
									WHERE  Orders=@Cnt;	
							 END
							 ELSE IF (CHARINDEX('C',@Send_Multi_Types) > 0 )
							 BEGIN
									UPDATE #Invoice_hdr_Distinct_Email_Addr_Temp set [Addressee_Type]='C' 
									WHERE  Orders=@Cnt;	
							 END	
							 ELSE IF (CHARINDEX('B',@Send_Multi_Types) > 0 )
							 BEGIN
									update #Invoice_hdr_Distinct_Email_Addr_Temp set [Addressee_Type]='B' 
									WHERE  Orders=@Cnt;	
							 END			 
						END
						ELSE
						BEGIN
							UPDATE #Invoice_hdr_Distinct_Email_Addr_Temp set [Addressee_Type]=@Send_Multi_Types 
							WHERE  Orders=@Cnt;	
						END
						SET @Cnt= @Cnt+1; 
						SET @Send_Multi_Types = '';
						SET @TmpEmail_Addr =''
					END; 


			   SELECT 
					 @strTo_Recipients  = coalesce(@strTo_Recipients + Email_Addr , Email_Addr ) + ';'
			   From #Invoice_hdr_Distinct_Email_Addr_Temp   Where  Addressee_Type = 'T'; 
			   SELECT  
					@strCc_Recipients  =  coalesce(@strCc_Recipients + Email_Addr , Email_Addr ) + ';'
			   From #Invoice_hdr_Distinct_Email_Addr_Temp   Where  Addressee_Type = 'C';
			   SELECT 
					 @strBcc_Recipients  = coalesce(@strBcc_Recipients + Email_Addr , Email_Addr ) + ';'
			   From #Invoice_hdr_Distinct_Email_Addr_Temp   Where  Addressee_Type = 'B';

			   SELECT @strTo_Recipients,@strCc_Recipients,@strBcc_Recipients
			     
				IF ( @strTo_Recipients is null )
				begin
					set @Error_Message ='E-Mail To address in not defined..'
				end

			----------------------- SELECT *FROM  #Invoice_hdr_Distinct_Email_Addr_Temp	
			DROP table #Invoice_hdr_Distinct_Email_Addr_Temp;
			DROP table #Invoice_hdr_All_Data ;
			DROP table #Invoice_hdr_Temp_Approver_1;
			DROP table #Invoice_hdr_Temp_Approver_2;


END
 




ELSE IF (@Record_Status ='Get_Email_Ids_Drilling_Dtl')
BEGIN
	 
		CREATE TABLE #All_Data_Drilling_Dtl ([Ord] int,Email_Addr varchar(300),Types  varchar(300),Addressee_Type varchar(300))
		/*--------------------------------------------------------------------------------------------------------------------*/
		/*For level 1 : only the RIG is considered*/
		SELECT  
			1 [Ord],	dbo.Fnc_Get_Col_Value('dbo.Mst_User',Approver_User_Id,'EMAIl')Email_Addr,
			'APPROVER_1'[Type] ,'C' [Addressee_Type] 
			INTO #Temp_Approver_1_Drilling_Dtl from  eos.Approver_Mapping map 
			INNER JOIN eos.Approval_Code cod on  map.Approval_Code_Id=cod.Approval_Code_Id
			INNER JOIN  eos.Approver_Mapping_Dtl mapApprover  on mapApprover.Approver_Mapping_Id = map.Approver_Mapping_Id
		WHERE Approver_Level= 1 
		AND Approver_Active= 'Y' and Approval_Active ='Y' and Approval_Code = @Approval_Code and 
		((@DB_USER_TYPE  ='CREATOR' AND 1=1) OR  (@DB_USER_TYPE <> 'CREATOR' AND Receive_Mail = 'Y'))/*this is for @Approval_Code='Drilling dtl*/
		AND Dept_Id IS NULL  AND Rig_Id = @Rig_Id 
		 
			
		if(@Event_Type ='FINALIZE')
		BEGIN
					IF(@DB_USER_TYPE  ='CREATOR' or  @DB_USER_TYPE  ='CREATOR,APPROVER_1') 
					BEGIN
						/*
						Alert_Ids
						-----------------------------------------------------------------------------------------------------------------
						|						Daily report				 	  
						-----------------------------------------------------------------------------------------------------------------

						238	 Drilling Dtl : Creation Mail					 
						239	 Daily Report : Level 1 approver Mail            
						-------------------------------------------------------    ---------------------------------------------------------
						*/ 
						
						INSERT INTO #All_Data_Drilling_Dtl 

						SELECT * FROM 
						(       /*Approver level 1*/
				 
								SELECT [Ord]  ,Email_Addr ,TYPE,'T' Addressee_Type FROM #Temp_Approver_1_Drilling_Dtl
						UNION 
							   /*Logged in User*/
								SELECT  2 [Ord] ,
								dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIl'),'Cur_Logged_In_User','C' [Addressee_Type]

						/*------------------------------------------Mail alert to user----------------------------------------------------*/		
						UNION
							  
								SELECT  3 [Ord],
								 RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type  FROM dbo.Mail_Alert_To_User 
								WHERE Alert_Id = 238  AND Mail_Alert_To IS NULL AND @Approval_Code = 'DRILLING_DTL'

					 		/*-----------------------------------------------------------------------------------------------------------------*/		
						)tb
						ORDER BY [Ord]
		 
					END

					IF(@DB_USER_TYPE  ='APPROVER_1' or  @DB_USER_TYPE  ='CREATOR,APPROVER_1') 
					BEGIN
					 
						INSERT INTO #All_Data_Drilling_Dtl 

						SELECT * FROM   
						(       /*Approver level 1*/
							 SELECT [Ord]  ,Email_Addr ,Type,'T' Addressee_Type From #Temp_Approver_1_Drilling_Dtl 	
							 /*----------------------------------------------MR and SR both----------------------------------------------------*/		
							 UNION
		
							 SELECT  2 [Ord] ,
								dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIL'),'daily_report_Created_By','C' [Addressee_Type]
								from eos.drilling_dtl WHERE  Drilling_Dtl_Id = @Drilling_Dtl_Id

						 
							/*-----------------------------------------------------------------------------------------------------------------*/		
							 UNION 
							    /*Logged in User*/
								SELECT  3 [Ord] ,
								dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIL'),'Cur_Logged_In_User','C' [Addressee_Type]

							 /*----------------------------------------------Mail_Alert_To_User----------------------------------------------------*/	
							 UNION
							    /*Employees added in alert table  */
								SELECT  4 [Ord],
								RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type  FROM dbo.Mail_Alert_To_User 
								WHERE Alert_Id = 239  AND Mail_Alert_To IS NULL AND @Approval_Code = 'DRILLING_DTL'
 		               	/*-----------------------------------------------------------------------------------------------------------------*/		
						)tb
						order by [Ord]
		 
					END
  
	
		END	  


		if(@Event_Type ='REVISE')
		BEGIN
					 
					IF(@DB_USER_TYPE  ='APPROVER_1' or  @DB_USER_TYPE  ='CREATOR,APPROVER_1') 
					BEGIN
					/*
					 */ 
						INSERT INTO #All_Data_Drilling_Dtl 

						SELECT * FROM   
						(       /*Approver level 1*/
							 SELECT [Ord]  ,Email_Addr ,Type,'T' Addressee_Type FROM #Temp_Approver_1_Drilling_Dtl 	
							 /*----------------------------------------------MR and SR both----------------------------------------------------*/		
							 UNION
		
							 SELECT  2 [Ord] ,
								dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIL'),'daily_report_Created_By','C' [Addressee_Type]
								from eos.drilling_dtl WHERE  Drilling_Dtl_Id = @Drilling_Dtl_Id

							/*-----------------------------------------------------------------------------------------------------------------*/		
							 UNION 
							    /*Logged in User*/
								SELECT  3 [Ord] ,
								dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIL'),'Cur_Logged_In_User','C' [Addressee_Type]

							 /*----------------------------------------------Mail_Alert_To_User----------------------------------------------------*/	
							 UNION
							    /*This is from alert table with Alert_id = 239 */
								SELECT  4 [Ord],
								RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type  FROM dbo.Mail_Alert_To_User 
								Where Alert_Id = 239  AND Mail_Alert_To IS NULL and @Approval_Code = 'DRILLING_DTL'

							 
							/*-----------------------------------------------------------------------------------------------------------------*/		
						)tb
						order by [Ord]
		 
					END
  
	
		END	  



	 
				select *,ROW_NUMBER() OVER(ORDER BY Email_Addr)[Orders],''[Addressee_Type] into #Distinct_Email_Addr_Temp_Drilling_Dtl
				from 
				(
						SELECT DISTINCT   Email_Addr       
						FROM #All_Data_Drilling_Dtl 
				)tb  
				---------------

				 
					DECLARE @Cnt_Drilling_Dtl int =1;
					SET  @Cnt_Drilling_Dtl =1;
					DECLARE @Cnt_Drilling_DtlMAX int = 0;
					SELECT @Cnt_Drilling_DtlMAX = COUNT(0) FROM #Distinct_Email_Addr_Temp_Drilling_Dtl;
					WHILE (@Cnt_Drilling_Dtl<=@Cnt_Drilling_DtlMAX)
					BEGIN
						--DECLARE @TmpEmail_Addr varchar(100)='';
						set @TmpEmail_Addr ='';

						SELECT  @TmpEmail_Addr= Email_Addr from  #Distinct_Email_Addr_Temp_Drilling_Dtl where Orders=@Cnt_Drilling_Dtl;		 		  
						--Declare @Send_Multi_Types  Varchar(7000)='';     									 
						set @Send_Multi_Types   =null;

						Select 			         			
						@Send_Multi_Types = Coalesce( @Send_Multi_Types +  cast(Addressee_Type as varchar(100)),
						cast(Addressee_Type as varchar(100)) ) + ','  					
			 			
						from 
						(	 
							select  Addressee_Type
							from  #All_Data_Drilling_Dtl  where Email_Addr = @TmpEmail_Addr
						)tb
			
						SET @Send_Multi_Types = SUBSTRING(@Send_Multi_Types,0,LEN(@Send_Multi_Types)-0)		
						--Select @Send_Multi_Types,@TmpEmail_Addr;

						IF(LEN(@Send_Multi_Types)>1)
						BEGIN 

							 IF ( CHARINDEX('T',@Send_Multi_Types) > 0 )			    
							 BEGIN
									UPDATE #Distinct_Email_Addr_Temp_Drilling_Dtl set [Addressee_Type]='T' 
									WHERE  Orders = @Cnt_Drilling_Dtl;	
							 END
							 ELSE IF (CHARINDEX('C',@Send_Multi_Types) > 0 )
							 BEGIN
									UPDATE #Distinct_Email_Addr_Temp_Drilling_Dtl set [Addressee_Type]='C' 
									WHERE  Orders = @Cnt_Drilling_Dtl;	
							 END	
							 ELSE IF (CHARINDEX('B',@Send_Multi_Types) > 0 )
							 BEGIN
									update #Distinct_Email_Addr_Temp_Drilling_Dtl set [Addressee_Type]='B' 
									WHERE  Orders=@Cnt_Drilling_Dtl;	
							 END			 
						END
						ELSE
						BEGIN
							UPDATE #Distinct_Email_Addr_Temp_Drilling_Dtl set [Addressee_Type]=@Send_Multi_Types 
							WHERE  Orders=@Cnt_Drilling_Dtl;	
						END
						SET @Cnt_Drilling_Dtl= @Cnt_Drilling_Dtl+1; 
						SET @Send_Multi_Types = '';
						SET @TmpEmail_Addr =''
					END; 


			   SELECT 
					 @strTo_Recipients  = coalesce(@strTo_Recipients + Email_Addr , Email_Addr ) + ';'
			   From #Distinct_Email_Addr_Temp_Drilling_Dtl   Where  Addressee_Type = 'T'; 
			   SELECT  
					@strCc_Recipients  =  coalesce(@strCc_Recipients + Email_Addr , Email_Addr ) + ';'
			   From #Distinct_Email_Addr_Temp_Drilling_Dtl   Where  Addressee_Type = 'C';
			   SELECT 
					 @strBcc_Recipients  = coalesce(@strBcc_Recipients + Email_Addr , Email_Addr ) + ';'
			   From #Distinct_Email_Addr_Temp_Drilling_Dtl   Where  Addressee_Type = 'B';

			   SELECT @strTo_Recipients,@strCc_Recipients,@strBcc_Recipients
			     
				IF ( @strTo_Recipients is null )
				begin
					set @Error_Message ='E-Mail To address in not defined..'
				end

		 
			DROP table #Distinct_Email_Addr_Temp_Drilling_Dtl;
			DROP table #All_Data_Drilling_Dtl ;
			DROP table #Temp_Approver_1_Drilling_Dtl;
			 

END
 
 
 ELSE IF (@Record_Status ='Get_Email_Ids_Mutual_Understand')
BEGIN
	 
		CREATE TABLE #All_Data_Mutual_Understand ([Ord] int,Email_Addr varchar(300),Types  varchar(300),Addressee_Type varchar(300))
		/*--------------------------------------------------------------------------------------------------------------------*/
		/*For level 1 : only the RIG is considered*/
		SELECT  
			1 [Ord],	dbo.Fnc_Get_Col_Value('dbo.Mst_User',Approver_User_Id,'EMAIl')Email_Addr,
			'APPROVER_1'[Type] ,'C' [Addressee_Type] 
			INTO #Temp_Approver_1_Mutual_Understand from  eos.Approver_Mapping map 
			INNER JOIN eos.Approval_Code cod on  map.Approval_Code_Id=cod.Approval_Code_Id
			INNER JOIN  eos.Approver_Mapping_Dtl mapApprover  on mapApprover.Approver_Mapping_Id = map.Approver_Mapping_Id
		WHERE Approver_Level= 1 
		AND Approver_Active= 'Y' and Approval_Active ='Y' and Approval_Code = @Approval_Code and 
		((@DB_USER_TYPE  ='CREATOR' AND Receive_Mail = 'Y')  OR  (@DB_USER_TYPE <> 'CREATOR' AND Receive_Mail = 'Y'))/*this can be MR_ON or SR_ON*/
		AND Dept_Id IS NULL  AND Rig_Id = @Rig_Id 
		 
			
		if(@Event_Type ='FINALIZE')
		BEGIN
					IF(@DB_USER_TYPE  ='CREATOR' or  @DB_USER_TYPE  ='CREATOR,APPROVER_1') 
					BEGIN
						/*
						Alert_Ids
						--------------------------------------------------------------------------------------------------------------
						|					Mutual understanding  addition	           						   
						----------------------------------------------------------------------------------------------------------------

						till now no alert added for Mutual understanding in table
						 		Mutual understanding : Creation Mail					 
						 		Mutual understanding : Level 1 approver Mail           
					 
						-------------------------------------------------------    ---------------------------------------------------------
						*/ 
						
						INSERT INTO #All_Data_Mutual_Understand 

						SELECT * FROM 
						(       /*Approver level 1*/
				 
								SELECT [Ord]  ,Email_Addr ,TYPE,'T' Addressee_Type FROM #Temp_Approver_1_Mutual_Understand
						UNION 
							   /*Logged in User*/
								SELECT  2 [Ord] ,
								dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIl'),'Cur_Logged_In_User','C' [Addressee_Type]

						/*---------------------------------------------if the email from ther database----------------------------------------------------*/		
						--UNION
						--	  /*Employees added in alert table  MATERIAL*/
						--		SELECT  3 [Ord],
						--		 RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type  FROM dbo.Mail_Alert_To_User 
						--		WHERE Alert_Id = 218  AND Mail_Alert_To IS NULL AND @Approval_Code = 'MUTUAL_UNDERSTAND'

					 	/*-----------------------------------------------------------------------------------------------------------------*/		
						)tb
						ORDER BY [Ord]
		 
					END

					IF(@DB_USER_TYPE  ='APPROVER_1' or  @DB_USER_TYPE  ='CREATOR,APPROVER_1') 
					BEGIN
					/*
					Alert_Ids
					208	Material Requisition : Level 2 approver Mail
					209	Material Requisition : Creation Mail
					210	Material Requisition : Level 1 approver Mail*/ 
						INSERT INTO #All_Data_Mutual_Understand 

						SELECT * FROM   
						(       /*Approver level 1*/
							 SELECT [Ord]  ,Email_Addr ,Type,'T' Addressee_Type From #Temp_Approver_1_Mutual_Understand 	
							 /*-----------------------------------------Mutual_Understanding created by User---------------------------------------------------*/		
							 UNION
		
							 SELECT  2 [Ord] ,
								dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIL'),'Mutual_Understand_Created_By','T' [Addressee_Type]
								from eos.Mutual_Understanding  WHERE  MU_Id = @MU_Id

							 		/*-----------------------------------------------------------------------------------------------------------------*/		
							 UNION 
							    /*Logged in User*/
								SELECT  3 [Ord] ,
								dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIL'),'Cur_Logged_In_User','C' [Addressee_Type]

							 /*--------------------------------------------- ---------------------------------------------------*/	
							 --UNION
							 --   /*Employees added in alert table MATERIAL*/
								--SELECT  4 [Ord],
								--RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type  FROM dbo.Mail_Alert_To_User 
								--Where Alert_Id = 219  AND Mail_Alert_To IS NULL and @Approval_Code = 'MUTUAL_UNDERSTAND'

						 				/*-----------------------------------------------------------------------------------------------------------------*/		
						)tb
						order by [Ord]
		 
					END
  
	
		END	  


		if(@Event_Type ='REVISE')
		BEGIN
					 
					IF(@DB_USER_TYPE  ='APPROVER_1' or  @DB_USER_TYPE  ='CREATOR,APPROVER_1') 
					BEGIN
					/*
					 */ 
						INSERT INTO #All_Data_Mutual_Understand 

						SELECT * FROM   
						(       /*Approver level 1*/
							 SELECT [Ord]  ,Email_Addr ,Type,'T' Addressee_Type From #Temp_Approver_1_Mutual_Understand 	
							 /*----------------------------------------------MR and SR both----------------------------------------------------*/		
							 UNION
		
							 SELECT  2 [Ord] ,
								dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIL'),'MUTUAL_UNDER_Created_By','T' [Addressee_Type]
								from eos.Mutual_Understanding WHERE  MU_Id = @MU_Id

							/*-----------------------------------------------------------------------------------------------------------------*/		
							 UNION 
							    /*Logged in User*/
								SELECT  3 [Ord] ,
								dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIL'),'Cur_Logged_In_User','C' [Addressee_Type]

							 /*----------------------------------------------Mail_Alert_To_User----------------------------------------------------*/	
							 --UNION
							 --   /*NO need to add this for now 01/08/2020*/
								--SELECT  4 [Ord],
								--RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type  FROM dbo.Mail_Alert_To_User 
								--Where Alert_Id = 219  AND Mail_Alert_To IS NULL and @Approval_Code = 'MUTUAL_UNDERSTAND'

							 
							/*-----------------------------------------------------------------------------------------------------------------*/		
						)tb
						order by [Ord]
		 
					END
  
	
		END	  
			   

				select *,ROW_NUMBER() OVER(ORDER BY Email_Addr)[Orders],''[Addressee_Type] into #Distinct_Email_Addr_Temp_Mutual_Understand
				from 
				(
						SELECT DISTINCT   Email_Addr       
						FROM #All_Data_Mutual_Understand 
				)tb  
				---------------

				----------------------------------------- select *  	FROM #All_Data_Mutual_Understand 
					DECLARE @CNT_MUTUAL_UNDERSTAND int =1;
					SET  @CNT_MUTUAL_UNDERSTAND =1;
					DECLARE @CNT_MUTUAL_UNDERSTANDMAX int = 0;
					SELECT @CNT_MUTUAL_UNDERSTANDMAX = COUNT(0) FROM #Distinct_Email_Addr_Temp_Mutual_Understand;
					WHILE (@CNT_MUTUAL_UNDERSTAND<=@CNT_MUTUAL_UNDERSTANDMAX)
					BEGIN
						--DECLARE @TmpEmail_Addr varchar(100)='';
						set @TmpEmail_Addr ='';

						SELECT  @TmpEmail_Addr= Email_Addr from  #Distinct_Email_Addr_Temp_Mutual_Understand
						where Orders=@CNT_MUTUAL_UNDERSTAND;		 		  
						--Declare @Send_Multi_Types  Varchar(7000)='';     									 
						set @Send_Multi_Types   =null;

						Select 			         			
						@Send_Multi_Types = Coalesce( @Send_Multi_Types +  cast(Addressee_Type as varchar(100)),
						cast(Addressee_Type as varchar(100)) ) + ','  					
			 			
						from 
						(	 
							select  Addressee_Type
							from  #All_Data_Mutual_Understand  where Email_Addr = @TmpEmail_Addr
						)tb
			
						SET @Send_Multi_Types = SUBSTRING(@Send_Multi_Types,0,LEN(@Send_Multi_Types)-0)		
						--Select @Send_Multi_Types,@TmpEmail_Addr;

						IF(LEN(@Send_Multi_Types)>1)
						BEGIN 

							 IF ( CHARINDEX('T',@Send_Multi_Types) > 0 )			    
							 BEGIN
									UPDATE #Distinct_Email_Addr_Temp_Mutual_Understand set [Addressee_Type]='T' 
									WHERE  Orders = @CNT_MUTUAL_UNDERSTAND;	
							 END
							 ELSE IF (CHARINDEX('C',@Send_Multi_Types) > 0 )
							 BEGIN
									UPDATE #Distinct_Email_Addr_Temp_Mutual_Understand set [Addressee_Type]='C' 
									WHERE  Orders = @CNT_MUTUAL_UNDERSTAND;	
							 END	
							 ELSE IF (CHARINDEX('B',@Send_Multi_Types) > 0 )
							 BEGIN
									update #Distinct_Email_Addr_Temp_Mutual_Understand set [Addressee_Type]='B' 
									WHERE  Orders=@CNT_MUTUAL_UNDERSTAND;	
							 END			 
						END
						ELSE
						BEGIN
							UPDATE #Distinct_Email_Addr_Temp_Mutual_Understand set [Addressee_Type]=@Send_Multi_Types 
							WHERE  Orders=@CNT_MUTUAL_UNDERSTAND;	
						END
						SET @CNT_MUTUAL_UNDERSTAND= @CNT_MUTUAL_UNDERSTAND+1; 
						SET @Send_Multi_Types = '';
						SET @TmpEmail_Addr =''
					END; 


			   SELECT 
					 @strTo_Recipients  = coalesce(@strTo_Recipients + Email_Addr , Email_Addr ) + ';'
			   From #Distinct_Email_Addr_Temp_Mutual_Understand   Where  Addressee_Type = 'T'; 
			   SELECT  
					@strCc_Recipients  =  coalesce(@strCc_Recipients + Email_Addr , Email_Addr ) + ';'
			   From #Distinct_Email_Addr_Temp_Mutual_Understand   Where  Addressee_Type = 'C';
			   SELECT 
					 @strBcc_Recipients  = coalesce(@strBcc_Recipients + Email_Addr , Email_Addr ) + ';'
			   From #Distinct_Email_Addr_Temp_Mutual_Understand   Where  Addressee_Type = 'B';

			   SELECT @strTo_Recipients,@strCc_Recipients,@strBcc_Recipients
			     
				IF ( @strTo_Recipients is null )
				begin
					set @Error_Message ='E-Mail To address in not defined (Approver 1 is not present)..'
				end

			----------------------- SELECT *FROM  #Distinct_Email_Addr_Temp_Mutual_Understand	
			DROP table #Distinct_Email_Addr_Temp_Mutual_Understand;
			DROP table #All_Data_Mutual_Understand ;
			DROP table #Temp_Approver_1_Mutual_Understand;
			--DROP table #Temp_Approver_2;

END

ELSE IF (@Record_Status ='Get_Email_Ids_Overtime_Details')
BEGIN
		/*	 
			251 Overtime: Creation Mail
			252	 Overtime : Level 1 approver Mail
			253 Overtime : Revise by Level 1 approver
			254 Overtime : Level 2 approver Mail
			255 Overtime : Revise by Level 2 approver

		---------------------------------------------------------------------------------------------

		Create : TO : approver1 list
			 CC: Creator User (Curent login user)
 			 BCC: DB alert  251		 
		---------------------------------------------------------------------------------------------
		Approver-1 : Finalise							  	Approver-2 : Finalise
			 TO : approver 2							     TO : approver 1
			 CC : Creator User(may be multiples)			 CC : Creator User(may be multiples)
			 BCC: DB alert  252								 BCC: DB alert 254 
		---------------------------------------------------------------------------------------------			
		Approver-1 : Revise Self							Approver-2 : Revise Self    
		        TO : User( may be multiples)				To : User( may be multiples)	
				cc : Self email								cc : Self email
		  	    BCC: DB alert  253							BCC: alert  255											
		
		Approver-1 : Revise previous level  			    Approver-2 : Revise previous level   
				 TO : User( may be multiples) 				To :User( may be multiples)	
			     BCC: alert  253				         	BCC: alert  255	
		-------------------------------------------------------------------------------------------------*/  

 
		CREATE TABLE #All_Data_Overtime ([Ord] int,Email_Addr varchar(300),Types  varchar(300),Addressee_Type varchar(300))
		/*--------------------------------------------------------------------------------------------------------------------*/
		/*For level 1 : only the RIG is considered*/
		SELECT  
			1 [Ord],	dbo.Fnc_Get_Col_Value('dbo.Mst_User',Approver_User_Id,'EMAIl')Email_Addr,
			'APPROVER_1'[Type] ,'C' [Addressee_Type] 
			INTO #Temp_Approver_1_Overtime from  eos.Approver_Mapping map 
			INNER JOIN eos.Approval_Code cod on  map.Approval_Code_Id=cod.Approval_Code_Id
			INNER JOIN  eos.Approver_Mapping_Dtl mapApprover  on mapApprover.Approver_Mapping_Id = map.Approver_Mapping_Id
		WHERE Approver_Level= 1 
		AND Approver_Active= 'Y' and Approval_Active ='Y' and Approval_Code = @Approval_Code and 
		((@DB_USER_TYPE  ='CREATOR' AND Receive_Mail = 'Y')  OR  (@DB_USER_TYPE <> 'CREATOR' AND Receive_Mail = 'Y'))/*this can be MR_ON or SR_ON*/
		AND Dept_Id IS NULL  AND Rig_Id = @Rig_Id 


		SELECT  
			1 [Ord],	dbo.Fnc_Get_Col_Value('dbo.Mst_User',Approver_User_Id,'EMAIl')Email_Addr,
			'APPROVER_2'[Type] ,'C' [Addressee_Type] 
			into #Temp_Approver_2_Overtime from  eos.Approver_Mapping map 
			INNER JOIN eos.Approval_Code cod on  map.Approval_Code_Id=cod.Approval_Code_Id
			INNER JOIN  eos.Approver_Mapping_Dtl mapApprover  on mapApprover.Approver_Mapping_Id = map.Approver_Mapping_Id
		WHERE Approver_Level= 2 
		AND Approver_Active= 'Y' AND Approval_Active ='Y' AND Approval_Code = @Approval_Code   AND 
		
		((@DB_USER_TYPE  ='CREATOR' AND Receive_Mail = 'Y') OR ( @DB_USER_TYPE <> 'CREATOR' AND Receive_Mail = 'Y'))/*this can be MR_ON or SR_ON*/
		  AND Rig_Id = @Rig_Id;
		  ----in this form Dept is not added as it is not requirnment ...........
		  
			
		if(@Event_Type ='FINALIZE')
		BEGIN
					IF(@DB_USER_TYPE  ='CREATOR') 
					BEGIN
						/*-------------------------------------
						Create : TO : approver 1 list
							 CC : Creator (Curent login user)
							 BCC: alert  251						 
						--------------------------------------*/ 						
						INSERT INTO #All_Data_Overtime 

						SELECT * FROM 
						(       /*Approver level 1*/
				 
									SELECT [Ord]  ,Email_Addr ,TYPE,'T' Addressee_Type FROM #Temp_Approver_1_Overtime
							UNION 
								   /*Logged in User*/
									SELECT  2 [Ord] ,
									dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIl'), 'List_Of_Users','C' [Addressee_Type]
									from eos.Overtime_Dtl where Overtime_Dtl_Id in(
									select  ID from[eos].[Fnc_Return_Table_For_ID](@strOvertime_Dtl_Ids))					
							UNION
							 
									SELECT  3 [Ord], RTRIM(LTRIM(Email_Addr)),'DataBase',  Addressee_Type  FROM dbo.Mail_Alert_To_User 
							   	    WHERE Alert_Id = 251  AND Mail_Alert_To IS NULL AND @Approval_Code = 'OVERTIME' 	
                            union
							 	SELECT 3 [Ord], dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIl'),'Cur_Logged_In_User','C' [Addressee_Type]	
						)tb
						ORDER BY [Ord]
		 
					END
					/*--------------------------------------						 
						Approver-1 : Finalise
						TO : approver-2
						CC : Creator User(may be multiples)
						BCC: DB alert  251
					--------------------------------------*/
					IF(@DB_USER_TYPE  ='APPROVER_1' ) 
					BEGIN
					 
						INSERT INTO #All_Data_Overtime 

						SELECT * FROM   
						(       /*Approver level 1*/
							 SELECT [Ord]  ,Email_Addr ,Type,'T' Addressee_Type From #Temp_Approver_2_Overtime 	
							 /*----------------------------------------------MR and SR both----------------------------------------------------*/		
							 UNION 

							 SELECT  2 [Ord] ,									 
								dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIl'), 'List_Of_Users','C' [Addressee_Type]
								FROM eos.Overtime_Dtl WHERE Overtime_Dtl_Id IN(
								SELECT  ID FROM[eos].[Fnc_Return_Table_For_ID](@strOvertime_Dtl_Ids)
								)							  
							 /*----------------------------------------------Mail_Alert_To_User----------------------------------------------------*/	
							 UNION
							    /*Employees added in alert table MATERIAL*/
								SELECT  3 [Ord],
								RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type  FROM dbo.Mail_Alert_To_User 
								WHERE Alert_Id = 252  AND Mail_Alert_To IS NULL AND @Approval_Code = 'OVERTIME'
 							union
							 	SELECT 3 [Ord], dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIl'),'Cur_Logged_In_User','C' [Addressee_Type]	
  
							/*-----------------------------------------------------------------------------------------------------------------*/		
						)tb
						order by [Ord]		 
					END
   

		           IF(@DB_USER_TYPE  ='APPROVER_2' ) 
					BEGIN
					 
						INSERT INTO #All_Data_Overtime 

						SELECT * FROM   
						(       /*Approver level 1*/
							 SELECT [Ord]  ,Email_Addr ,Type,'T' Addressee_Type From #Temp_Approver_1_Overtime 	
							 /*----------------------------------------------MR and SR both----------------------------------------------------*/		
							 UNION							 
							 SELECT  2 [Ord] ,									 
								dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIl'), 'List_Of_Users','C' [Addressee_Type]
								FROM eos.Overtime_Dtl WHERE Overtime_Dtl_Id IN(
								SELECT  ID FROM[eos].[Fnc_Return_Table_For_ID](@strOvertime_Dtl_Ids)
								)							  
							 /*----------------------------------------------Mail_Alert_To_User----------------------------------------------------*/	
							 UNION
							    /*Employees added in alert table MATERIAL*/
								SELECT  3 [Ord],
								RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type  FROM dbo.Mail_Alert_To_User 
								Where Alert_Id = 254  AND Mail_Alert_To IS NULL and @Approval_Code = 'OVERTIME'
	 						 UNION
							 	SELECT 3 [Ord], dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIl'),'Cur_Logged_In_User','C' [Addressee_Type]	
							/*-----------------------------------------------------------------------------------------------------------------*/		
						)tb
						order by [Ord]
		 
					END
		END	  

		if(@Event_Type ='REVISE' or @Event_Type ='DELETE')
		BEGIN					 
					 
				IF(@DB_USER_TYPE  ='APPROVER_1') 
				BEGIN
					  IF(@SubFilter_Hierarchy='L1')--EMAIL to SELF
					  BEGIN
							INSERT INTO #All_Data_Overtime 
							SELECT * FROM   
							(        
									/*Logged in User*/
									SELECT 1 [Ord], dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIl')Email_Addr,
									'Cur_Logged_In_User'[Type],'T' [Addressee_Type]							 
 	
	   	 					)tb1
							ORDER BY [Ord];		 
					 END	------SELF
					 ELSE
					 BEGIN --email OTHER PREVIOUS LEVEL

							INSERT INTO #All_Data_Overtime 
							SELECT * FROM   
							( 
							        SELECT  1 [Ord] ,									 
									dbo.Fnc_Get_Col_Value('dbo.Mst_User',Cr_User_Id,'EMAIL')Email_Addr,'List_Of_Users'[Type],
									'T' [Addressee_Type] FROM eos.Overtime_Dtl WHERE Overtime_Dtl_Id IN(
									SELECT  ID FROM[eos].[Fnc_Return_Table_For_ID](@strOvertime_Dtl_Ids))
																	
									UNION
									/*Employees added in alert table MATERIAL*/
									SELECT  2 [Ord],
									RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type FROM dbo.Mail_Alert_To_User 
									Where Alert_Id = 253  AND Mail_Alert_To IS NULL and @Approval_Code = 'OVERTIME'
							
									UNION 
									/*Logged in User*/
									SELECT 3 [Ord], dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIl'),'Cur_Logged_In_User','C' [Addressee_Type]
									UNION 
									SELECT [Ord]  ,Email_Addr ,TYPE,'T' Addressee_Type FROM #Temp_Approver_1_Overtime



	   	 					)tb
							order by [Ord];		 
					 END	------s
				END



				IF(@DB_USER_TYPE  ='APPROVER_2') 
				BEGIN
					  IF(@SubFilter_Hierarchy='L2')--EMAIL to SELF
					  BEGIN

							INSERT INTO #All_Data_Overtime 
							SELECT * FROM   
							(        
									/*Logged in User*/
									SELECT 1 [Ord], dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIl')Email_Addr,
									'Cur_Logged_In_User'[Type],'T' [Addressee_Type]								 
 	
	   	 					)tb1
							ORDER BY [Ord];		 
					 END	------SELF
					 ELSE
					 BEGIN --email OTHER PREVIOUS LEVEL

							INSERT INTO #All_Data_Overtime 
							SELECT * FROM   
							( 							
							        /*Approver level 2*/
									SELECT 1 [Ord]  ,Email_Addr ,Type,'T' Addressee_Type From #Temp_Approver_1_Overtime 	
									/*----------------------------------------------MR and SR both----------------------------------------------------*/		
									UNION							       
									/*Employees added in alert table MATERIAL*/
									SELECT  2 [Ord],
									RTRIM(LTRIM(Email_Addr)),'DataBase',Addressee_Type FROM dbo.Mail_Alert_To_User 
									Where Alert_Id = 255  AND Mail_Alert_To IS NULL and @Approval_Code = 'OVERTIME'
							
									UNION 
									/*Logged in User*/
									SELECT 3 [Ord], dbo.Fnc_Get_Col_Value('dbo.Mst_User',@Cur_Logged_In_User_Id,'EMAIl'),'Cur_Logged_In_User','C' [Addressee_Type]
 	
	   	 					)tb
							order by [Ord];		 
					 END	------s
				END 
		END	   

			---================================================================================================================


				select *,ROW_NUMBER() OVER(ORDER BY Email_Addr)[Orders],''[Addressee_Type] into #Distinct_Email_Addr_Temp_Overtime
				from 
				(
						SELECT DISTINCT   Email_Addr       
						FROM #All_Data_Overtime 
				)tb  
				---------------

				----------------------------------------- select *  	FROM #All_Data_Overtime 
					 DECLARE @Cnt_Overtime int =1;
					SET  @Cnt_Overtime =1;
					 DECLARE @Cnt_OvertimeMAX int = 0;
					SELECT @Cnt_OvertimeMAX = COUNT(0) FROM #Distinct_Email_Addr_Temp_Overtime;
					WHILE (@Cnt_Overtime<=@Cnt_OvertimeMAX)
					BEGIN
					 
						set @TmpEmail_Addr ='';

						SELECT  @TmpEmail_Addr= Email_Addr from  #Distinct_Email_Addr_Temp_Overtime where Orders=@Cnt_Overtime;		 		  
					 
						set @Send_Multi_Types   =null;

						Select 			         			
						@Send_Multi_Types = Coalesce( @Send_Multi_Types +  cast(Addressee_Type as varchar(100)),
						cast(Addressee_Type as varchar(100)) ) + ','  					
			 			
						from 
						(	 
							select  Addressee_Type
							from  #All_Data_Overtime  where Email_Addr = @TmpEmail_Addr
						)tb
			
						SET @Send_Multi_Types = SUBSTRING(@Send_Multi_Types,0,LEN(@Send_Multi_Types)-0)		
					 
						IF(LEN(@Send_Multi_Types)>1)
						BEGIN 

							 IF ( CHARINDEX('T',@Send_Multi_Types) > 0 )			    
							 BEGIN
									UPDATE #Distinct_Email_Addr_Temp_Overtime set [Addressee_Type]='T' 
									WHERE  Orders = @Cnt_Overtime;	
							 END
							 ELSE IF (CHARINDEX('C',@Send_Multi_Types) > 0 )
							 BEGIN
									UPDATE #Distinct_Email_Addr_Temp_Overtime set [Addressee_Type]='C' 
									WHERE  Orders = @Cnt_Overtime;	
							 END	
							 ELSE IF (CHARINDEX('B',@Send_Multi_Types) > 0 )
							 BEGIN
									update #Distinct_Email_Addr_Temp_Overtime set [Addressee_Type]='B' 
									WHERE  Orders=@Cnt_Overtime;	
							 END			 
						END
						ELSE
						BEGIN
							UPDATE #Distinct_Email_Addr_Temp_Overtime set [Addressee_Type]=@Send_Multi_Types 
							WHERE  Orders=@Cnt_Overtime;	
						END
						SET @Cnt_Overtime= @Cnt_Overtime+1; 
						SET @Send_Multi_Types = '';
						SET @TmpEmail_Addr =''
					END; 


			   SELECT 
					 @strTo_Recipients  = coalesce(@strTo_Recipients + Email_Addr , Email_Addr ) + ';'
			   From #Distinct_Email_Addr_Temp_Overtime   Where  Addressee_Type = 'T'; 
			   SELECT  
					@strCc_Recipients  =  coalesce(@strCc_Recipients + Email_Addr , Email_Addr ) + ';'
			   From #Distinct_Email_Addr_Temp_Overtime   Where  Addressee_Type = 'C';
			   SELECT 
					 @strBcc_Recipients  = coalesce(@strBcc_Recipients + Email_Addr , Email_Addr ) + ';'
			   From #Distinct_Email_Addr_Temp_Overtime   Where  Addressee_Type = 'B';

			   SELECT @strTo_Recipients,@strCc_Recipients,@strBcc_Recipients
			     
				IF ( @strTo_Recipients is null )
				begin
					set @Error_Message ='E-Mail To address in not defined (Approver 1 is not present)..'
				end

			----------------------- SELECT *FROM  #Distinct_Email_Addr_Temp_Overtime	
			DROP table #Distinct_Email_Addr_Temp_Overtime;
			DROP table #All_Data_Overtime ;
			DROP table #Temp_Approver_1_Overtime;
			 


END

/*Approver wise Revise mechanism is not to be add in offer and contarct letter

 while explaining case today 08/08/2019*/
--ELSE IF (@Record_Status ='REVISE_OFFER_LETTER')
--	Begin
--			--L2 => L2, L2,L1,C1
--			--L1 => L1, L1,C1
--			--If (@SubFilter_Hierarchy ='L2' or @SubFilter_Hierarchy ='L2_L1_C1')
--			--BEGIN
--			--		UPDATE eos.Material_Requisition_Hdr
--			--		SET					

--			--			L2_Approval_Status			=   'N',
--			--			L2_Approval_Dt				=   NULL,
--			--			L2_User_Id					=   NULL,
--			--			L2_User_Name				=   NULL,
--			--			L2_Working_Designation_Id   =   NULL,
--			--			L2_Remarks					=	NULL,			
															
--			--			Opened_For_Revision_By	  = @Opened_For_Revision_By,
--			--			Opened_For_Revision_Dt= getdate()
--			--		WHERE MR_Hdr_Id = @MR_Hdr_Id
--			--END

--			If (@SubFilter_Hierarchy ='L1' or @SubFilter_Hierarchy ='L1_C1' or @SubFilter_Hierarchy ='L2_L1_C1')
--			BEGIN
--					UPDATE eos.Fs_Offer_Letter
--					SET 
						  
--						L1_Approval_Status			=   'N',
--						L1_Approval_Dt				=   NULL,
--						L1_User_Id					=   NULL,
						 
						 			 										
--						Opened_For_Revision_By	  = @Opened_For_Revision_By,
--						Opened_For_Revision_Dt    = getdate()
--					WHERE MR_Hdr_Id = @MR_Hdr_Id
--			END

--		    If (@SubFilter_Hierarchy ='L1_C1' or @SubFilter_Hierarchy ='L2_L1_C1')
--			BEGIN
--					UPDATE eos.Material_Requisition_Hdr
--					SET 						 
--						Cr_Status				  = 'N',						 								 										
--						Opened_For_Revision_By	  = @Opened_For_Revision_By,
--						Opened_For_Revision_Dt    = getdate()
--					WHERE MR_Hdr_Id = @MR_Hdr_Id
--			END
			
--	end
Else
	Begin
		RAISERROR('Invalid parameter for record status provided...', 16, 1)
	End




End
